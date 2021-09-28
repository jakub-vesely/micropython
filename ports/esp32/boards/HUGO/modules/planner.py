import uasyncio

class Planner:
  async def _async_postpone(self, delay_s, function, *args, **kwargs):
    await uasyncio.sleep(delay_s)
    function(*args, **kwargs)

  def postpone(self, delay_s, function, *args, **kwargs):
    uasyncio.create_task(self._async_postpone(delay_s, function, *args, **kwargs))

  async def _async_repeat(self, delay_s, function, *args, **kwargs):
    function(*args, **kwargs)
    await uasyncio.sleep(delay_s)
    uasyncio.create_task(self._async_repeat(delay_s, function, *args, **kwargs))

  def repeat(self, delay_s, function, *args, **kwargs):
    uasyncio.create_task(self._async_repeat(delay_s, function, *args, **kwargs))

  async def _async_main(self):
    while True:
      await uasyncio.sleep_ms(1000)

  def run(self):
    uasyncio.run(self._async_main())
