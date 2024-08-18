#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

from micropython import const
from blocks.block_base import BlockBase
from blocks.block_types import BlockType

_get_ext_count_command =      const(0xf9)
_get_ext_address_command =    const(0xfa)
_change_ext_address_command = const(0xfb)
_get_ext_addr_count_command = const(0xfc)
_get_ext_addr_list_command =  const(0xfd)

class ExtendedBlockBase(BlockBase):

  def get_extension_count(self) -> int:
    data = self._tiny_read_base_id(_get_ext_count_command, None, 1)
    return data[0] if data else None


  def get_ext_address_list(self) -> bytes:
    count_data = self._tiny_read_base_id(_get_ext_addr_count_command, None, 1)
    if not count_data:
      return None

    data =  self._tiny_read_base_id(_get_ext_addr_list_command, None, count_data[0])
    return list(data) if data else None

  def get_extension_address(self) -> int:
    address_data = self._tiny_read_base_id(_get_ext_address_command, None, 1)
    return address_data[0] if address_data else None

  def change_extension_address(self, address:int) -> bool:
    return self._tiny_read_base_id(_change_ext_address_command, bytes([address]), 1)

  def _ext_write(self, ext_address: int, data: bytes):
    try:
      if ext_address:
        self.i2c.writeto(ext_address, data)
    except OSError:
      self.logging.error("ext address 0x%02X is unavailable for writing", ext_address)

  def _ext_read(self, ext_address: int, in_data: bytes=None, expected_length: int=0):
    if ext_address is None:
        return None
    self._ext_write(ext_address, in_data)
    try:
      return self.i2c.readfrom(ext_address, expected_length, True)
    except OSError:
      self.logging.error("ext address 0x%02X is unavailable for reading", ext_address)
      return None

class BlockWithOneExtension(ExtendedBlockBase):
  def __init__(self, type_id: BlockType, address: int):
    super().__init__(type_id, address)
    self.ext_address = self.get_extension_address() if self.is_available() else None

  def change_extension_address(self, address:int) -> bool:
    if super().change_extension_address(address):
      self.ext_address = address
      return True
    return False

  def _one_ext_write(self, data: bytes):
    if self.ext_address:
      self._ext_write(self.ext_address, data)

  def _one_ext_read(self, in_data: bytes=None, expected_length: int=0):
    if self.ext_address:
      return self._ext_read(self.ext_address, in_data, expected_length)
    return None
