#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

from logging import Logging
from power_mgmt import PowerMgmt
import sys
import time
import uasyncio

logging = Logging("planner")
unhandled_exception_prefix = "Unhandled exception"


class TaskProperties:
  kill = False
  waiting_start_ms = 0
  waiting_time_ms = 0

class Planner:
  _performed_tasks = {} #expected dict with task handle as key and tasks properties as value
  _handle_count = 0
  _loop = uasyncio.get_event_loop()
  _power_mgmt = PowerMgmt()

  @classmethod
  def _get_next_handle(cls):
    handle = cls._handle_count
    cls._handle_count += 1
    return handle

  @classmethod
  async def _async_plan(cls, handle, function, *args, **kwargs):
    if not cls._performed_tasks[handle].kill:
      try:
        function(*args, **kwargs)
      except Exception as error:
        logging.exception(error, extra_message=unhandled_exception_prefix)
    del cls._performed_tasks[handle]

  @classmethod
  def plan(cls, function, *args, **kwargs):
    handle = cls._get_next_handle()
    cls._performed_tasks[handle] = TaskProperties()
    cls._loop.create_task(cls._async_plan(handle, function, *args, **kwargs))
    return handle

  @classmethod
  async def _task_sleep(cls, handle, delay_s):
    task = cls._performed_tasks[handle]
    task.waiting_start_ms = time.ticks_ms()
    task.waiting_time_ms = int(delay_s * 1000)
    while time.ticks_ms() < task.waiting_start_ms + task.waiting_time_ms and not task.kill:
      await uasyncio.sleep_ms(0) # give chance another task

    task.waiting_time_ms = 0

  @classmethod
  async def _async_postpone(cls, handle, delay_s, function, *args, **kwargs):
    await cls._task_sleep(handle, delay_s)
    if not cls._performed_tasks[handle].kill:
      try:
        function(*args, **kwargs)
      except Exception as error:
        logging.exception(error, extra_message=unhandled_exception_prefix)
    del cls._performed_tasks[handle]

  @classmethod
  def postpone(cls, delay_s, function, *args, **kwargs):
    handle = cls._get_next_handle()
    cls._performed_tasks[handle] = TaskProperties()
    cls._loop.create_task(cls._async_postpone(handle, delay_s, function, *args, **kwargs))
    return handle
  @classmethod
  async def _async_repeat(cls, handle, delay_s, function, *args, **kwargs):
    if not cls._performed_tasks[handle].kill:
      try:
        function(*args, **kwargs)
      except Exception as error:
        logging.exception(error, extra_message=unhandled_exception_prefix)
      await cls._task_sleep(handle, delay_s) # in case of kill task is created and the kill feature is tested when is executed
      cls._loop.create_task(cls._async_repeat(handle, delay_s, function, *args, **kwargs))
    else:
      del cls._performed_tasks[handle]

  @classmethod
  def repeat(cls, delay_s, function, *args, **kwargs):
    handle = cls._get_next_handle()
    cls._performed_tasks[handle] = TaskProperties()
    cls._loop.create_task(cls._async_repeat(handle, delay_s, function, *args, **kwargs))
    return handle

  @classmethod
  async def _async_main(cls):
    while True:
      now = time.ticks_ms()
      remains_min = sys.maxsize
      for properties in cls._performed_tasks.values():
        if properties.kill or properties.waiting_time_ms == 0: #tasks dedicated to be killed and tasks that do not have set any waiting are skipped
          continue

        remains = properties.waiting_time_ms - (now - properties.waiting_start_ms)
        if remains < remains_min:
          remains_min = remains

      if remains_min == sys.maxsize or remains_min <= 0:
        await uasyncio.sleep_ms(0)
      elif not cls._power_mgmt.is_power_save_enabled() or remains_min < 100:
        await uasyncio.sleep_ms(remains_min)
      else:
        #print("light_sleep for %d ms" % remains_min)
        cls._power_mgmt.light_sleep(remains_min)

  @classmethod
  def run(cls):
    cls._loop.run_until_complete(cls._async_main())

  @classmethod
  def kill_task(cls, handle):
    if handle in cls._performed_tasks:
      cls._performed_tasks[handle].kill = True
