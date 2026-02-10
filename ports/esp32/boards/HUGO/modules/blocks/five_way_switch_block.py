#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

from blocks.block_types import BlockTypes
from blocks.block_base import BlockBase
from basal.active_variable import ActiveVariable
from micropython import const   # type: ignore
from basal.logging import Logging

_i2c_command_button_id = const(1)
_i2c_command_button_value = const(2)

class FiveWaySwitchBlock(BlockBase):
  states = (
      "none",
      "left",
      "right",
      "up",
      "down",
      "press"
  )
  button_none = states[0]
  button_left = states[1]
  button_right = states[2]
  button_up = states[3]
  button_down = states[4]
  button_press = states[5]


  def __init__(self, address=None, measurement_period: float=0.1):
    super().__init__(BlockTypes.button, address)  # type: ignore
    self.value = ActiveVariable(False, measurement_period, self._button_id)

  def _button_id(self):
    # for adjusting boundary numbers
    # data =  self._tiny_read(_i2c_command_button_value, None, 1)
    # if (data is not None):
    #   self.logging.info("button value:%d" % data[0])
    button_id = self._tiny_read(_i2c_command_button_id, None, 1)
    if button_id is None or len(button_id) != 1:
      return self.button_none

    return self.states[button_id[0]]

  def get_button_raw_value(self):
    raw_value = self._tiny_read(_i2c_command_button_value, None, 1)
    if raw_value is None or len(raw_value) != 1:
      return 0

    return raw_value[0];
