#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

from basal.logging import Logging
from basal.power_mgmt import PowerMgmt
import sys
import time
import uasyncio
import gc

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
    task = cls._performed_tasks[handle]
    #PowerMgmt.block_power_save() #just for case a uasyncio.sleep is used in a library
    if not task.kill:
      try:
        function(*args, **kwargs)
      except Exception as error:
        logging.exception(error, extra_message=unhandled_exception_prefix)
    #PowerMgmt.unblock_power_save()
    del cls._performed_tasks[handle]

  @classmethod
  def plan(cls, function, *args, **kwargs):
    """
    Plans the task to be executed within the task loop
    The function name have to be placed without brackets to do not be called instead of storing
    """
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
    if not task.kill:
      task.waiting_time_ms = 0 #to do not be gone to light_sleep before caller task is finished

  @classmethod
  async def _async_postpone(cls, handle, delay_s, function, *args, **kwargs):
    task = cls._performed_tasks[handle]
    await cls._task_sleep(handle, delay_s)
    #PowerMgmt.block_power_save()
    if not task.kill:
      try:
        function(*args, **kwargs)
      except Exception as error:
        logging.exception(error, extra_message=unhandled_exception_prefix)
    #PowerMgmt.unblock_power_save()
    del cls._performed_tasks[handle]


  @classmethod
  def postpone(cls, delay_s, function, *args, **kwargs):
    """
    Plans the task to be executed with the defined delay
    The function name have to be placed without brackets to do not be called instead of storing
    """
    handle = cls._get_next_handle()
    cls._performed_tasks[handle] = TaskProperties()
    cls._loop.create_task(cls._async_postpone(handle, delay_s, function, *args, **kwargs))
    return handle

  @classmethod
  async def _async_repeat(cls, handle, delay_s, function, *args, **kwargs):
    task = cls._performed_tasks[handle]
    if not task.kill:
      #PowerMgmt.block_power_save()
      try:
        function(*args, **kwargs)
      except Exception as error:
        logging.exception(error, extra_message=unhandled_exception_prefix)
      #PowerMgmt.unblock_power_save()
      await cls._task_sleep(handle, delay_s) # in case of kill task is created and the kill feature is tested when is executed

      #PowerMgmt.block_power_save() #to will not be lightsleep called now
      cls._loop.create_task(cls._async_repeat(handle, delay_s, function, *args, **kwargs))
      #PowerMgmt.unblock_power_save()
    else:
      del cls._performed_tasks[handle]

  @classmethod
  def repeat(cls, delay_s, function, *args, **kwargs):
    """
    Plans the task to be repeated with the defined period, first call will be planned without the delay
    The function name have to be placed without brackets to do not be called instead of storing
    """
    handle = cls._get_next_handle()
    cls._performed_tasks[handle] = TaskProperties()
    cls._loop.create_task(cls._async_repeat(handle, delay_s, function, *args, **kwargs))
    return handle

  @classmethod
  def _calculate_minimal_remaining_time(cls):
    now = time.ticks_ms()
    remains_min = sys.maxsize
    for properties in cls._performed_tasks.values():
      if properties.kill:
        continue
      remains = properties.waiting_time_ms - (now - properties.waiting_start_ms)
      #print("remains " + str(remains))
      if remains < remains_min:
        remains_min = remains
    return remains_min

  @classmethod
  async def _async_main(cls):
    while True:
      remains_min = cls._calculate_minimal_remaining_time()
      if remains_min == sys.maxsize or remains_min <= 0:
        await uasyncio.sleep_ms(10) # to gove chance another task to do what they need
        continue

      light_sleep_limit = 100
      if remains_min > light_sleep_limit: #we have plenty of time lets use it for cleaning
        gc.collect()
        #print(micropython.mem_info())
        remains_min = cls._calculate_minimal_remaining_time()

      if not cls._power_mgmt.is_power_save_enabled() or remains_min <= light_sleep_limit:
        await uasyncio.sleep_ms(remains_min) #I can asleep this routine, another tasks will still continue
      else:
        print("light_sleep for %d ms" % (remains_min - light_sleep_limit))
        cls._power_mgmt.light_sleep(remains_min - light_sleep_limit)
        await uasyncio.sleep_ms(0) #return to another planned tasks

  @classmethod
  def run(cls):
    """
    Starts the planner. this method is called automatically when the program starts
    """
    cls._loop.run_until_complete(cls._async_main())

  @classmethod
  def kill_task(cls, handle):
    """
    Kills planned task to will not be performed or repeated. Returns True if the task was found and marked as killed, False otherwise.
    """
    if handle in cls._performed_tasks:
      cls._performed_tasks[handle].kill = True
      return True
    return False

