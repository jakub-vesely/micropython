#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

from blocks.block_types import BlockTypes
from blocks.block_base import BlockBase

class RgbLedBlockCommand():
  set_rgb = 1 # followed by 3 bytes (RGB)
  set_color = 2 # foloowd by the color code
  set_on = 3
  set_off = 4

class Rgb():
  def __init__(self, red, green, blue) -> None:
    self.red = red
    self.green = green
    self.blue = blue

class RgbLedBlockColor():
  black = Rgb(0, 0, 0)
  white = Rgb(255, 255, 255)
  red = Rgb(255, 0, 0)
  green = Rgb(0, 255, 0)
  blue = Rgb(0, 0, 255)
  yellow = Rgb(255, 225, 0)
  purple = Rgb(255, 0, 255)
  cyan = Rgb(0, 255, 255)
  orange = Rgb(255, 127, 0)
  greenyellow = Rgb(127, 255, 0)
  skyblue = Rgb(0, 127, 255)
  aquamarine = Rgb(0, 255, 127)
  magenta = Rgb(255, 0, 127)
  violet = Rgb(127, 0, 255)

class RgbLedBlock(BlockBase):
  colors = (
      RgbLedBlockColor.black,
      RgbLedBlockColor.white,
      RgbLedBlockColor.red,
      RgbLedBlockColor.green,
      RgbLedBlockColor.blue,
      RgbLedBlockColor.yellow,
      RgbLedBlockColor.purple,
      RgbLedBlockColor.cyan,
      RgbLedBlockColor.orange,
      RgbLedBlockColor.greenyellow,
      RgbLedBlockColor.skyblue,
      RgbLedBlockColor.aquamarine,
      RgbLedBlockColor.magenta,
      RgbLedBlockColor.violet
  )

  def __init__(self, address=None):
    super().__init__(BlockTypes.rgb, address)
    self.state = False

  def toggle(self):
    if self.state:
      self.set_off()
    else:
      self.set_on()

  def set_rgb(self, red: int, green: int, blue: int):
    self._tiny_write(
        RgbLedBlockCommand.set_rgb,
        red.to_bytes(1, 'big') + green.to_bytes(1, 'big') + blue.to_bytes(1, 'big')
    )
    self.state = (red or green or blue)

  def set_color(self, color: RgbLedBlockColor):
    self.set_rgb(color.red, color.green, color.blue)

  def set_color_by_id(self, index: int):
    if index < len(self.colors):
      self.set_rgb(self.colors[index].red, self.colors[index].green, self.colors[index].blue)

  def set_on(self):
    self.set_rgb(RgbLedBlockColor.white.red, RgbLedBlockColor.white.green, RgbLedBlockColor.white.blue)

  def set_off(self):
    self.set_rgb(RgbLedBlockColor.black.red, RgbLedBlockColor.black.green, RgbLedBlockColor.black.blue)
