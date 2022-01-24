#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

from block_types import BlockTypes
from extended_block_base import BlockWithOneExtension
from block_base import PowerSaveLevel
from active_variable import ActiveVariable
from micropython import const
from vl53l1x import VL53L1X

class DistanceBlock(BlockWithOneExtension):

  def __init__(self, address: int=None, measurement_period: float=1):
    """
    @param address:block address
    @param measurement_period: sampling frequency in sec
    """
    super().__init__(BlockTypes.distance, address)
    #self.is_usb_connected = ActiveVariable(False, measurement_period, self._get_usb_state)
    self._vl53l1 = VL53L1X(self.i2c, self.ext_address)
    self.distance = ActiveVariable(0, measurement_period, self._get_distance)

  def _get_distance(self):
    if self.block_type_valid and self.power_save_level == PowerSaveLevel.NoPowerSave:
      return self._vl53l1.read()
    return 0

  def power_save(self, level:PowerSaveLevel) -> None:
    super().power_save(level)
    if level == PowerSaveLevel.NoPowerSave:
      self._vl53l1.init()
