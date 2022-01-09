#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

import ssd1306
import uasyncio
import math
from extended_block_base import BlockWithOneExtension
from active_variable import ActiveVariable

class DisplayBlock(BlockWithOneExtension):
  _get_dimmensions_command = 0x03

  def __init__(self, address=None, invert=False):
    super().__init__(self.type_display, address)

    dimensions = self.get_dimensions()

    if not self.ext_address:
      self.logging.error("display is not available")
      self._display = None
      return

    try:
      self._display = ssd1306.SSD1306_I2C(dimensions[0], dimensions[1], self.i2c, self.ext_address)
    except Exception as error:
      self.logging.exception(error, extra_message="ssd1306 was not initialized")

  def change_extension_address(self, address:int) -> bool:
    if super().change_extension_address(address):
      self._display.addr = address
      return True
    else:
      return False

  def get_ssd_i2c_address(self):
    return self.get_extension_address()

  def get_dimensions(self):
    """
    returns display dimmensions as tuple (x, y). If dimensions are not provided is returned tuple (0,0)
    """
    dimensions_data = self._tiny_read(self._get_dimmensions_command, None, 2)
    return (dimensions_data[0], dimensions_data[1]) if dimensions_data and len(dimensions_data) == 2 else (0, 0)

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

  def draw_ellipse(self, x, y, rh, rv, color=1):
    """
    @param x: x center coordinate
    @param y: y center coordinate
    @param rh: horizontal radius
    @param rv vertical radius
    """
    for pos in range(0, rh):
      normalized = pos / rh
      val = int(round(math.sqrt(1.0 - normalized * normalized) * rv, 0))
      self._display.pixel(x + pos, y - val, color)
      self._display.pixel(x - pos, y - val, color)
      self._display.pixel(x + pos, y + val, color)
      self._display.pixel( x - pos, y + val, color)

    for pos in range(0, rv):
      normalized = pos / rv
      val = int(round(math.sqrt(1.0 - normalized * normalized) * rh, 0))
      self._display.pixel(x + val, y - pos, color);
      self._display.pixel(x - val, y - pos, color);
      self._display.pixel(x + val, y + pos, color);
      self._display.pixel(x - val, y + pos, color);

  def print_text(self, x0, y0, text, color=1):
    self._display.text(text, x0, y0, color)
