#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

from blocks.block_types import BlockTypes
from blocks.extended_block_base import BlockWithOneExtension
from blocks.block_base import PowerSaveLevel
from basal.active_variable import ActiveVariable
from vl53l1x import VL53L1X

class DistanceBlock(BlockWithOneExtension):

  def __init__(self, address: int=None, measurement_period: float=1):
    """
    @param address:block address
    @param measurement_period: sampling frequency in sec
    """
    super().__init__(BlockTypes.distance, address)
    #self.is_usb_connected = ActiveVariable(False, measurement_period, self._get_usb_state)
    self.value = ActiveVariable(0, measurement_period, self._get_distance)

    #doesn't make sense to initialize extension when the block is not inserted
    self._vl53l1 = VL53L1X(self.i2c, self.ext_address) if self.is_available() else None

  def _get_distance(self):
    if self._vl53l1 and self.power_save_level == PowerSaveLevel.NoPowerSave:
      return self._vl53l1.read()
    return 0

  def power_save(self, level:PowerSaveLevel) -> None:
    super().power_save(level)
    if self._vl53l1 and level == PowerSaveLevel.NoPowerSave:
      self._vl53l1.init()
