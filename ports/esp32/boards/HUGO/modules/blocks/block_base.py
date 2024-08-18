#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

import machine   # type: ignore
import time
from micropython import const   # type: ignore
import typing

from basal.logging import Logging
from blocks.block_types import BlockType

_power_save_command = const(0xf6)
_get_module_version_command = const(0xf7)
_change_i2c_address_command =  const(0xfe)
_i2c_block_type_id_base = const(0xFA)

class PowerSaveLevel:
  NoPowerSave = 0    # powersave is off
  LightPowerSave = 1 # subsystems that are not needed are turned off
  DeepPowerSave = 2  # all subsystems are turned off

class BlockBase:
  i2c = machine.I2C(0, scl=machine.Pin(22), sda=machine.Pin(21), freq=100000)

  def __init__(self, block_type: BlockType, address: int):
    self.type_id = block_type.id
    self.address = address if address else block_type.id #default block i2c address is equal to its block type

    self.block_type_valid = False
    self.logging = Logging(block_type.name.decode("utf-8"))
    self.block_version = self._get_block_version()

    self.power_save_level = PowerSaveLevel.NoPowerSave
    self._tiny_write_base_id(_power_save_command, self.power_save_level.to_bytes(1, 'big'), True) #wake up block functionality

    if not self.block_version:
      self.logging.warning("module with address 0x%x is not available", self.address)
    elif self.block_version[0] != self.type_id:
      self.logging.error("unexpected block type. expected: %d, returned: %d", self.type_id, self.block_version[0])
    else:
      self.block_type_valid = True

  def _raw_tiny_write(self, type_id: int, command: int, data=None, silent=False):
    try:
      payload = type_id.to_bytes(1, 'big') + command.to_bytes(1, 'big')

      if data:
        payload += data
      #self.logging.info(("write", payload))
      self.i2c.writeto(self.address, payload)
    except OSError:
      if not silent:
        self.logging.error("tiny-block with address 0x%02X is unavailable for writing", self.address)

  def _check_type(self, type_id):
    return type_id in (_i2c_block_type_id_base, self.type_id) and (_i2c_block_type_id_base or self.block_type_valid)

  def __tiny_write_common(self, type_id: int, command: int, data=None, silent=False):
    """
    writes data to tiny_block via I2C
    @param type_id: block type id
    @param command: one byte command
    @param data: specify input data for entered command
    """
    if self._check_type(type_id):
      self._raw_tiny_write(type_id, command, data, silent)
    else:
      self.logging.error("invalid block type - writing interupted")

  def _tiny_write_base_id(self, command: int, data=None, silent=False):
    self.__tiny_write_common(_i2c_block_type_id_base, command, data, silent)

  def _tiny_write(self, command: int, data=None, silent=False):
    if not self.is_available():
      return
    self.__tiny_write_common(self.type_id, command, data, silent)

  def __tiny_read_common(self, type_id: int, command: int, in_data: typing.Union[bytes,None]=None, expected_length: int=-1, silent=False):
    """
    reads data form tiny_block via I2C
    @param type_id: block type id
    @param command: one byte command
    @param in_data: specify input data for entered command
    @param expected_length: if defined (> 0)will be read entered number of bytes. If None is expected length as a first byte
    @return provided bytes. If size is first byte is not included to output data
    """
    if self._check_type(type_id):
      self._raw_tiny_write(type_id, command, in_data, silent)
      try:
        if expected_length > 0:
          data = self.i2c.readfrom(self.address, expected_length, True)
        else:
          data = self.i2c.readfrom(self.address, 255, True)
          data = data[1: data[0]+1]

        return data
      except OSError:
        if not silent:
          self.logging.error("tiny-block with address 0x%02X is unavailable for reading", self.address)
      return None
    else:
      self.logging.error("invalid block type - reading interupted")
      return None

  def _tiny_read_base_id(self, command: int, in_data: typing.Union[bytes,None]=None, expected_length: int=-1, silent=False):
    return self.__tiny_read_common(_i2c_block_type_id_base, command, in_data, expected_length, silent)

  def _tiny_read(self, command: int, in_data: typing.Union[bytes,None]=None, expected_length: int=-1):
    if not self.is_available():
      return None

    return self.__tiny_read_common(self.type_id, command, in_data, expected_length)

  def change_block_address(self, new_address):
    self._tiny_write_base_id(_change_i2c_address_command, new_address.to_bytes(1, 'big'))
    self.address = new_address
    time.sleep(0.1) #wait to the change is performed and stopped

  def _get_block_version(self):
    """
    returns block_type, pcb version, adjustment_version
    """
    data = self._tiny_read_base_id(_get_module_version_command, None, 3, silent=True)
    if not data:
      return b""
    return (data[0], data[1], data[2])

  def is_available(self):
    return self.block_type_valid #available and valid block version

  def power_save(self, level:int) -> None:
    """
    level is aPowerSaveLevel value
    """
    self.power_save_level = level
    self._tiny_write_base_id(_power_save_command, level.to_bytes(1, 'big'))
