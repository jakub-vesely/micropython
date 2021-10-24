import uasyncio
import sys
from logging import Logging

logging = Logging("planner")
unhandled_exception_prefix = "Unhandled exception"

async def _async_plan(function, *args, **kwargs):
  try:
    function(*args, **kwargs)
  except Exception as error:
    logging.exception(error, extra_message=unhandled_exception_prefix)

def plan(function, *args, **kwargs):
  uasyncio.create_task(_async_plan(function, *args, **kwargs))

async def _async_postpone(delay_s, function, *args, **kwargs):
  await uasyncio.sleep(delay_s)
  try:
    function(*args, **kwargs)
  except Exception as error:
    logging.exception(error, extra_message=unhandled_exception_prefix)

def postpone(delay_s, function, *args, **kwargs):
  uasyncio.create_task(_async_postpone(delay_s, function, *args, **kwargs))

async def _async_repeat(delay_s, function, *args, **kwargs):
  try:
    function(*args, **kwargs)
  except Exception as error:
    logging.exception(error, extra_message=unhandled_exception_prefix)

  await uasyncio.sleep(delay_s)
  uasyncio.create_task(_async_repeat(delay_s, function, *args, **kwargs))

def repeat(delay_s, function, *args, **kwargs):
  uasyncio.create_task(_async_repeat(delay_s, function, *args, **kwargs))

async def _async_main():
  while True:
    await uasyncio.sleep_ms(1000)

def run():
  uasyncio.run(_async_main())
