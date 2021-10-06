import uasyncio
import machine

class BlockBase:
  change_i2c_address_command =  0xfe

  i2c_block_type_id_base = 0xFA

  i2c = machine.I2C(0, scl=machine.Pin(22), sda=machine.Pin(21), freq=100000)
  i2c_lock = uasyncio.Lock()

  def __init__(self, type_id: int, address: int):
    self.type_id = type_id
    self.address = address

  async def _unsafe_async_tiny_write(self, type_id: int, command: int, data=None):
    try:
      payload = type_id.to_bytes(1, 'big') + command.to_bytes(1, 'big')

      if data:
        payload += data
      #print(payload)
      self.i2c.writeto(self.address, payload)
    except OSError:
      print("tiny-block with address 0x%02X is unavailable for writing" % self.address)

  async def _async_tiny_write(self, type_id: int, command: int, data=None):
    async with self.i2c_lock:
      await self._unsafe_async_tiny_write(self.type_id, command, data)

  def tiny_write(self, command: int, data: int=None):
    uasyncio.create_task(self._async_tiny_write(self.type_id, command, data))

  async def _async_tiny_read(self, type_id: int, command: int, in_data: bytes=None, expected_length: int=0):
    async with self.i2c_lock:
      await self._unsafe_async_tiny_write(type_id, command, in_data)
      try:
        return self.i2c.readfrom(self.address, expected_length, True)
      except OSError:
        print("tiny-block with address 0x%02X is unavailable for reading" % self.address)
      return None

  def tiny_reader(self, command: int, in_data: int=None, expected_length=None) -> bytes:
    """
    reads data form tyiny_block ia I2C
    @param command:one byte command
    @param in_data: specify input data for entered command
    @param expected_length: if defined will be read entered number of bytes. If None is expected length as a first byte
    @return provided bytes. If size is first byte is not included to output data
    """
    uasyncio.create_task(self._async_tiny_read(self.type_id, command, in_data, expected_length))

  async def _async_change_block_address(self, new_address):
    await self._async_tiny_write(
      self.i2c_block_type_id_base, self.change_i2c_address_command, new_address.to_bytes(1, 'big')
    )
    self.address = new_address

  def change_block_address(self, new_address):
    uasyncio.create_task(self._async_change_block_address(new_address))