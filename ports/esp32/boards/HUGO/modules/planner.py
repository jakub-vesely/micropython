import uasyncio
import sys
from logging import Logging
class Planner:
  logging = Logging("planner")
  _unhandled_exception_prefix = "Unhandled exception"

  async def _async_plan(self, function, *args, **kwargs):
    try:
      function(*args, **kwargs)
    except Exception as error:
      self.logging.exception(error, extra_message=self._unhandled_exception_prefix)

  def plan(self, function, *args, **kwargs):
    uasyncio.create_task(self._async_plan(function, *args, **kwargs))

  async def _async_postpone(self, delay_s, function, *args, **kwargs):
    await uasyncio.sleep(delay_s)
    try:
      function(*args, **kwargs)
    except Exception as error:
      self.logging.exception(error, extra_message=self._unhandled_exception_prefix)

  def postpone(self, delay_s, function, *args, **kwargs):
    uasyncio.create_task(self._async_postpone(delay_s, function, *args, **kwargs))

  async def _async_repeat(self, delay_s, function, *args, **kwargs):
    try:
      function(*args, **kwargs)
    except Exception as error:
      self.logging.exception(error, extra_message=self._unhandled_exception_prefix)

    await uasyncio.sleep(delay_s)
    uasyncio.create_task(self._async_repeat(delay_s, function, *args, **kwargs))

  def repeat(self, delay_s, function, *args, **kwargs):
    uasyncio.create_task(self._async_repeat(delay_s, function, *args, **kwargs))

  async def _async_main(self):
    while True:
      await uasyncio.sleep_ms(1000)

  def run(self):
    uasyncio.run(self._async_main())
