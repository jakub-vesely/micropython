#  Copyright (c) 2024 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

from blocks.block_types import BlockTypes
from blocks.block_base import BlockBase

class ServoBlock(BlockBase):
  set_value_command = 1
  def __init__(self, address=None):
    super().__init__(BlockTypes.servo, address)
    self.state = False

  def set_value(self, value:int):
    self._tiny_write(self.set_value_command, value.to_bytes(1, 'big'))
