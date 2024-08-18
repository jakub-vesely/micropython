#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

from blocks.block_types import BlockTypes
from blocks.extended_block_base import BlockWithOneExtension
from blocks.block_base import PowerSaveLevel
from basal.active_variable import ActiveVariable
from basal.active_quantity import ActiveQuantity
from quantities.temperature import Temperature
from quantities.humidity import RelativeHumidity
from quantities.pressure import Pressure
from bme280_float import BME280

class AmbientBlock(BlockWithOneExtension):

  def __init__(self, address: int=None, measurement_period: float=10):
    """
    @param address:block address
    @param measurement_period: sampling frequency in sec
    """
    super().__init__(BlockTypes.ambient, address)
    self._value = ActiveVariable((None, None, None), measurement_period, self._get_value)
    self._value.updated(self._fill_values)
    self.temperature = ActiveQuantity(Temperature(precision=3), change_threshold=0.1);
    self.pressure = ActiveQuantity(Pressure(precision=3), change_threshold=100);
    self.humidity = ActiveQuantity(RelativeHumidity(precision=3), change_threshold=0.1);

    #doesn't make sense to initialize extension when the block is not inserted
    self._bme280 = BME280(i2c=self.i2c) if self.is_available() else None

  @property
  def value(self):
    return self._value

  def _get_value(self):
    if self._bme280 and self.power_save_level == PowerSaveLevel.NoPowerSave:
      t, p, h  = self._bme280.read_compensated_data()
      return (t, p, h)


  def _fill_values(self):
    self.temperature.set(self._value.get()[0])
    self.pressure.set(self._value.get()[1])
    self.humidity.set(self._value.get()[2])

  def power_save(self, level:PowerSaveLevel) -> None:
    super().power_save(level)
    #TODO
