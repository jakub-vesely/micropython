import ssd1306
import uasyncio
import math
from extended_block_base import ExtendedBlockBase
from active_variable import ActiveVariable

class DisplayBlock(ExtendedBlockBase):
  type_id_display =0x05
  _get_dimmensions_command = 0x03

  def __init__(self, address, invert=False):
    super().__init__(self.type_id_display, address)
    print("dimensions", self.get_dimensions())

    display_address = self.get_extension_address()
    print("display_address", display_address)
    self._display = ssd1306.SSD1306_I2C(64, 48, self.i2c, display_address)


  def get_ssd_i2c_address(self):
    return self.get_extension_address()

  async def _async_get_dimensions(self):
    dimensions_data = await self._async_tiny_read(self.type_id_display, self._get_dimmensions_command, None, 2)
    return (dimensions_data[0], dimensions_data[1]) if dimensions_data and len(dimensions_data) == 2 else (0, 0)

  def get_dimensions(self):
    """
    returns display dimmensions as tuple (x, y). If dimensions are not provided is returned tuple (0,0)
    """
    return uasyncio.get_event_loop().run_until_complete(self._async_get_dimensions())

  async def _async_power_on(self, power_on):
    if power_on:
      self._display().poweron()
    else:
      self._display().poweroff()

  def power_on(self, power_on:bool):
    uasyncio.create_task(self._async_power_on(power_on))

  async def _async_invert(self, invert):
    self._display.invert(invert)

  def invert(self, invert:bool):
    uasyncio.create_task(self._async_invert(invert))

  async def _async_rotate(self, value:bool):
    self._display.rotate(not value)

  def rotate(self, value:bool):
    uasyncio.create_task(self._async_rotate(value))

  async def _async_contrast(self, value:int):
    """
    param: contrast in range 0..255
    """
    self._display.contrast(value)

  def contrast(self, value:bool):
    uasyncio.create_task(self._async_contrast(value))

  async def _async_showtime(self):
    async with self.i2c_lock:
      self._display.show()

  def showtime(self):
    uasyncio.create_task(self._async_showtime())

  def clean(self):
    self._display.fill(0)

  def draw_point(self, x, y, color=1):
    self._display.pixel(x, y, color)

  def draw_line(self, x0, y0, x1, y1, color=1):
    self._display.line(x0, y0, x1,y1, color)

  def draw_rect(self, x0, y0, width, height, color=1):
    self._display.rect(x0, y0, width, height, color)

  def fill_rect(self, x0, y0, width, height, color=1):
    self._display.fill_rect(x0, y0, width, height, color)

  def draw_elipse(self, x, y, r1, r2, color=1):
    for pos in range(0, r1):
      normalized = pos / r1
      val = int(round(math.sqrt(1.0 - normalized * normalized) * r2, 0))
      self._display.pixel(x + pos, y - val, color)
      self._display.pixel(x - pos, y - val, color)
      self._display.pixel(x + pos, y + val, color)
      self._display.pixel( x - pos, y + val, color)

    for pos in range(0, r2):
      normalized = pos / r2
      val = int(round(math.sqrt(1.0 - normalized * normalized) * r1, 0))
      self._display.pixel(x + val, y - pos, color);
      self._display.pixel(x - val, y - pos, color);
      self._display.pixel(x + val, y + pos, color);
      self._display.pixel(x - val, y + pos, color);

  def print_text(self, x0, y0, text, color=1):
    self._display.text(text, x0, y0, color)
