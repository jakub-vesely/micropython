import uasyncio
from block_base import BlockBase

class ExtendedBlockBase(BlockBase):
  get_ext_count_command =       0xf9
  get_ext_address_command =     0xfa
  change_ext_address_command =  0xfb
  get_ext_addr_count_command =  0xfc
  get_ext_addr_list_command =   0xfd

  def __init__(self, type_id: int, address: int):
    super(type_id, address)

  async def _async_get_extension_count(self):
    return await self._async_tiny_read(
      self.i2c_block_type_id_base, self.get_ext_count_command, None, 1
    )
  def get_extension_count(self) -> int:
    return uasyncio.get_event_loop().run_until_complete(self._async_get_extension_count())

  async def _async_get_ext_address_list(self, order):
    count_data = await self._async_tiny_read(
      self.i2c_block_type_id_base, self.get_ext_addr_count_command, bytes([order]), 1
    )
    return await self._async_tiny_read(
      self.i2c_block_type_id_base, self.get_ext_addr_list_command, bytes([order]), count_data[0]
    )

  def get_ext_address_list(self, order=0) -> bytes:
    return uasyncio.get_event_loop().run_until_complete(self._async_get_ext_address_list(order))

  async def _async_get_extension_address(self):
    address_data = await self._async_tiny_read(
      self.i2c_block_type_id_base, self.get_ext_address_command, None, 1
    )
    return address_data[0] if address_data else None

  def get_extension_address(self, index=0) -> int:
    return uasyncio.get_event_loop().run_until_complete(self._async_get_extension_address())

  async def _async_change_extension_address(self, extension, address):
    return await self._async_tiny_read(
      self.i2c_block_type_id_base, self.change_ext_address_command, bytes([extension, address]), 1
    )
  def change_extension_address(self, extension:int,  address:int) -> bool:
    return uasyncio.get_event_loop().run_until_complete(self._async_change_extension_address(extension, address))