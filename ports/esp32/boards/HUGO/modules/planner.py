import uasyncio
from logging import Logging

logging = Logging("planner")
unhandled_exception_prefix = "Unhandled exception"

handle_count = 0
killers = list()
loop = uasyncio.get_event_loop()

def kill(handle):
  global killers
  killers.append(handle)

def _remove_killer(handle):
  if handle in killers:
    killers.remove(handle)
    return True
  return False

def _get_next_handle():
  global handle_count
  handle = handle_count
  handle_count += 1
  return handle

async def _async_plan(handle, function, *args, **kwargs):
  if not _remove_killer(handle):
    try:
      function(*args, **kwargs)
    except Exception as error:
      logging.exception(error, extra_message=unhandled_exception_prefix)

def plan(function, *args, **kwargs):
  handle = _get_next_handle()
  loop.create_task(_async_plan(handle, function, *args, **kwargs))
  return handle

async def _async_postpone(handle, delay_s, function, *args, **kwargs):
  await uasyncio.sleep(delay_s)
  if not _remove_killer(handle):
    try:
      function(*args, **kwargs)
    except Exception as error:
      logging.exception(error, extra_message=unhandled_exception_prefix)

def postpone(delay_s, function, *args, **kwargs):
  handle = _get_next_handle()
  loop.create_task(_async_postpone(handle, delay_s, function, *args, **kwargs))
  return handle

async def _async_repeat(handle, delay_s, function, *args, **kwargs):
  if not _remove_killer(handle):
    try:
      function(*args, **kwargs)
    except Exception as error:
      logging.exception(error, extra_message=unhandled_exception_prefix)

    await uasyncio.sleep(delay_s)
    loop.create_task(_async_repeat(handle, delay_s, function, *args, **kwargs))

def repeat(delay_s, function, *args, **kwargs):
  handle = _get_next_handle()
  loop.create_task(_async_repeat(handle, delay_s, function, *args, **kwargs))
  return handle

async def _async_main():
  while True:
    await uasyncio.sleep_ms(1) #just to be started scheduled task TODO: power efficiency

def run():
  loop.run_until_complete(_async_main())
