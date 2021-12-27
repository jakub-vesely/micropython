from math import trunc
from extended_block_base import BlockWithOneExtension
from active_variable import ActiveVariable

class PowerBlock(BlockWithOneExtension):
  _charging_state_command = 0x01

  ina219_mode_shunt_bus_continuous = 0b111
  na219_sadc_8sam_4260 = 0b1011
  ina219_badc_res_12bit = 0b0011
  ina219_pg_gd4_160mv = 0b10
  ina219_brng_16v = 0

  ina219_configuration_command = 0x00
  ina219_shunt_voltage_command = 0x01
  ina219_busvoltag_command = 0x02
  ina219_power_command = 0x03
  ina219_current_command = 0x04
  ina219_calibration_command = 0x05

  shunt_r = 0.1

  def __init__(self, address: int=None, measurement_period: float=1):
    super().__init__(self.type_power, address)
    self.is_usb_connected = ActiveVariable(False, measurement_period, self._get_usb_state)
    self.is_charging = ActiveVariable(False, measurement_period, self._get_charging_state)
    self.battery_voltage_V = ActiveVariable(0, measurement_period, self._get_voltage)
    self.battery_current_mA = ActiveVariable(0, measurement_period, self._get_current_ma)
    self._ina_init()

  def _ina_init(self):
    config = self.ina219_mode_shunt_bus_continuous
    config |= self.na219_sadc_8sam_4260 << 3
    config |= self.ina219_badc_res_12bit << 7
    config |= self.ina219_pg_gd4_160mv << 11
    config |= self.ina219_brng_16v << 13
    #reset bit is 0

    data = config.to_bytes(2, 'big', False)
    data = self.ina219_configuration_command.to_bytes(1, "big", False) + data
    self._one_ext_write(data)

  def _get_usb_state(self) -> int:
    if self.block_version[1] < 2 and self.block_version[2] < 1:
      return -1 #not implemented for this version

    state = self._tiny_read(self._charging_state_command, None, 1)
    self.logging.info("_get_usb_state: %s, %d", str(state), state[0] >> 1)
    return state[0] >> 1

  def _get_charging_state(self) -> int:
    state = self._tiny_read(self._charging_state_command, None, 1)
    return state[0] & 1

  def _get_voltage(self) -> float:
    data = self._one_ext_read(self.ina219_busvoltag_command.to_bytes(1, "big", False), 2)
    raw_voltage = ((data[0] << 8) | data[1]) >> 3
    return  raw_voltage * 0.004 #LSB = 4 mV

  def _get_current_ma(self) -> float:
    data = self._one_ext_read(self.ina219_shunt_voltage_command.to_bytes(1, "big", False), 2)
    raw_voltage = (data[0] << 8) | data[1]
    if data[0] & 0x80:
      self.logging.info("curren raw", raw_voltage)
      raw_voltage = ((raw_voltage - 1) ^ 0xffff) * -1
    return raw_voltage * (0.01 / self.shunt_r) #LSB = 10 uV
