#  Copyright (c) 2024 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

from blocks.block_types import BlockTypes
from blocks.block_base import BlockBase
from basal.active_variable import ActiveVariable

class StepMotorBlock(BlockBase):
  _set_target_pos_command = 1
  _get_actual_pos_command = 2
  _get_steps_per_turn = 3
  _reset_command = 4
  _calibrate_command = 5
  _calibration_done = 6

  def __init__(self, address=None, measurement_period: float=0.1):
    super().__init__(BlockTypes.step_motor, address)
    self.state = False
    self.target_position = 0
    self.step_per_turn = self.get_steps_per_turn()
    self.value = ActiveVariable(False, measurement_period, self._get_actual_position)
    self.logging.info("steps per_turn:", self.step_per_turn)

  def on_target(self):
    return self.value.get() == self.target_position

  def set_target_position(self, value:int):
    self.target_position = value;
    self._tiny_write(self._set_target_pos_command, value.to_bytes(2, 'big'))

  def get_actual_position(self, force:bool=False) -> int:
    self.value.get(force)

  def _get_actual_position(self) -> int:
    data =  self._tiny_read(self._get_actual_pos_command, None, 2)
    if data:
      value = (data[0] << 8) + data[1]
      return (value ^ 0x8000) - 0x8000
    return 0

  def get_actual_angle_deg(self, force:bool=False) -> int:
    position = self.value.get(force)
    if self.step_per_turn:
      return (position % self.step_per_turn) / self.step_per_turn * 360
    else:
      return 0

  def set_target_angle_deg(self, value:float):
    self.set_target_position(int(value / 360 * self.step_per_turn))

  def reset(self):
    self._tiny_write(self._reset_command)

  def calibrate(self):
    self._tiny_write(self._calibrate_command)

  def get_steps_per_turn(self):
    data =  self._tiny_read(self._get_steps_per_turn, None, 2)
    if data:
      return (data[0] << 8) + data[1]
    return 0
