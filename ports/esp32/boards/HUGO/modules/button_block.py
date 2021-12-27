from block_base import BlockBase
from active_variable import ActiveVariable
class ButtonBlock(BlockBase):
  _is_pressed_command = 0x01
  def __init__(self, address=None, measurement_period: float=1):
    super().__init__(self.type_buttom, address)
    self.is_pressed = ActiveVariable(False, measurement_period, self._is_pressed)

  def _is_pressed(self):
    data =  self._tiny_read(self._is_pressed_command, None, 1)
    #self.logging.info(("data", data))
    return False if data[0] else True #negative logic