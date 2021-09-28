import uasyncio
import machine

class BlockBase:
  change_i2c_address_command = 0xFE
  i2c_block_type_id_base = 0xFA

  i2c = machine.I2C(0, scl=machine.Pin(22), sda=machine.Pin(21), freq=100000)
  i2c_lock = uasyncio.Lock()
  def __init__(self, type_id: int, address: int):
    self.type_id = type_id
    self.address = address
  async def _async_tiny_setter(self, type_id: int, command: int, data=None):
    async with self.i2c_lock:
      try:
        payload = type_id.to_bytes(1, 'big') + command.to_bytes(1, 'big')

        if data:
          payload += data
        #print(payload)
        self.i2c.writeto(self.address, payload)
      except OSError:
        print("tiny-block with address 0x%02X is unavailable" % self.address)

  def tiny_setter(self, command: int, data: int=None):
    uasyncio.create_task(self._async_tiny_setter(self.type_id, command, data))

  async def _async_change_block_address(self, new_address):
    await self._async_tiny_setter(
      self.i2c_block_type_id_base,
      self.change_i2c_address_command,
      new_address.to_bytes(1, 'big')
    )
    self.address = new_address

  def change_block_address(self, new_address):
    uasyncio.create_task(self._async_change_block_address(new_address))
