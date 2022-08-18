#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

from micropython import const
from blocks.block_types import BlockTypes
from blocks.extended_block_base import BlockWithOneExtension
from basal.active_variable import ActiveVariable
from basal.active_quantity import ActiveQuantity
from quantities.current import Current
from quantities.voltage import Voltage

_charging_state_command = const(0x01)

_ina219_mode_shunt_bus_continuous = const(0b111)
_ina219_sadc_8sam_4260 = const(0b1011)
_ina219_badc_res_12bit = const(0b0011)
_ina219_pg_gd4_160mv = const(0b10)
_ina219_brng_16v = const(0b00)

_ina219_configuration_command = const(0x00)
_ina219_shunt_voltage_command = const(0x01)
_ina219_busvoltag_command = const(0x02)

#reset bit is 0
_config = const(_ina219_mode_shunt_bus_continuous | (_ina219_sadc_8sam_4260 << 3) | (_ina219_badc_res_12bit << 7) | (_ina219_pg_gd4_160mv << 11) | (_ina219_brng_16v << 13))

#_ina219_power_command = const(0x03)
#_ina219_current_command = const(0x04)
#_ina219_calibration_command = const(0x05)

_shunt_r = 0.1

class PowerBlock(BlockWithOneExtension):

  def __init__(self, address: int=0, measurement_period: float=1):
    """
    @param address:block address
    @param mesurement_period: sampling frequency in sec
    """
    super().__init__(BlockTypes.power, address)
    self.is_usb_connected = ActiveVariable(False, measurement_period, self._get_usb_state)
    self.is_charging = ActiveVariable(False, measurement_period, self._get_charging_state)
    self.battery_voltage = ActiveQuantity(Voltage(), 0, measurement_period, self._get_voltage)
    self.battery_current = ActiveQuantity(Current(), 0, measurement_period, self._get_current_A)

    self._ina_init()

  def _ina_init(self):
    if not self.ext_address:
      return

    data = _config.to_bytes(2, 'big', False)
    data = _ina219_configuration_command.to_bytes(1, "big", False) + data
    self._one_ext_write(data)

  def _get_usb_state(self) -> int:
    if not self.ext_address:
      return 0

    if self.block_version[1] < 2 and self.block_version[2] < 1:
      return -1 #not implemented for this version

    state = self._tiny_read(_charging_state_command, None, 1)
    if state is None:
      return 0
    return state[0] >> 1

  def _get_charging_state(self) -> int:
    if not self.ext_address:
      return 0

    state = self._tiny_read(_charging_state_command, None, 1)
    if state is None:
      return 0
    return state[0] & 1

  def _get_voltage(self) -> float:
    data = self._one_ext_read(_ina219_busvoltag_command.to_bytes(1, "big", False), 2)
    if not data:
      return 0
    raw_voltage = ((data[0] << 8) | data[1]) >> 3
    return  raw_voltage * 0.004 #LSB = 4 mV

  def _get_current_A(self) -> float:
    data = self._one_ext_read(_ina219_shunt_voltage_command.to_bytes(1, "big", False), 2)
    if not data:
      return 0
    raw_voltage = (data[0] << 8) | data[1]
    negative = True
    if data[0] & 0x80:
      raw_voltage = ((raw_voltage - 1) ^ 0xffff)
      negative = False
    abs_value = raw_voltage * (0.01 / _shunt_r) * 1e-3 #LSB = 10 uV
    return abs_value * -1 if negative else abs_value
