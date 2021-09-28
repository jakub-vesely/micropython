from block_base import BlockBase
from active_variable import ActiveVariable

class RgbBlockCommand():
    set_rgb = 1 # followed by 3 bytes (RGB)
    set_color = 2 # foloowd by the color code
    set_on = 3
    set_off = 4

class RgbBlockColor():
  black = 1
  white = 2
  red = 3
  green = 4
  blue = 5
  yellow = 6
  purple = 7
  cyan = 8
  orange = 9
  greenyellow = 10
  skyblue = 11
  aquamarine = 12
  magenta = 13
  violet = 14

class RgbBlock(BlockBase):
  type_id_rgb = 0x02

  def __init__(self, address):
    super().__init__(self.type_id_rgb, address)
    self.state = ActiveVariable(False)

  def toggle(self):
    if self.state:
      self.tiny_setter(RgbBlockCommand.set_off)
    else:
      self.tiny_setter(RgbBlockCommand.set_on)
    self.state.set_value(not self.state)

  def set_rgb(self, red: int, green: int, blue: int):
    self.tiny_setter(
        RgbBlockCommand.set_rgb,
        red.to_bytes(1, 'big') + green.to_bytes(1, 'big') + blue.to_bytes(1, 'big')
    )
    self.state.set_value(red or green or blue)

  def set_color(self, color: int):
    print("set_color")
    self.tiny_setter(RgbBlockCommand.set_color, color.to_bytes(1, 'big'))
    self.state.set_value(color != RgbBlockColor.black)

  def set_on(self):
    self.tiny_setter(RgbBlockCommand.set_on)
    self.state.set_value(True)

  def set_off(self):
    self.tiny_setter(RgbBlockCommand.set_off)
    self.state.set_value(False)
