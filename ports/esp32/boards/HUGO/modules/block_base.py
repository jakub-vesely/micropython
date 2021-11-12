from logging import Logging
import machine
import time

class BlockType:
  def __init__(self, type: int, name: str):
    self.id = type
    self.name = name

class BlockBase:
  type_power = BlockType(0x01, "power_block")
  type_rgb = BlockType(0x02, "rgb_block")
  type_motor_driver = BlockType(0x03, "motor_block")
  # type_id_ir = BlockType(0x04, "ir_block")
  type_display = BlockType(0x05, "disp_block")

  get_module_version_command = 0xf7
  change_i2c_address_command =  0xfe

  i2c_block_type_id_base = 0xFA

  i2c = machine.I2C(0, scl=machine.Pin(22), sda=machine.Pin(21), freq=100000)

  def __init__(self, block_type: int, address: int):
    self.type_id = block_type.id
    self.address = address
    self.logging = Logging(block_type.name)
    self.block_type_valid = True
    self.block_version = self._get_block_version()
    if self.block_version[0] != self.type_id:
      self.logging.error("unexpected block type. expected: %d, returned: %d", self.type_id, self.block_version[0])
      self.block_type_valid = False

  def _raw_tiny_write(self, type_id: int, command: int, data=None):
    try:
      payload = type_id.to_bytes(1, 'big') + command.to_bytes(1, 'big')

      if data:
        payload += data
      #print(("payload", payload))
      #print(("self.address", self.address))
      self.i2c.writeto(self.address, payload)
    except OSError:
      self.logging.error("tiny-block with address 0x%02X is unavailable for writing", self.address)

  def _check_type(self, type_id):
    return type_id in (self.i2c_block_type_id_base, self.type_id) and (self.i2c_block_type_id_base or self.block_type_valid)

  def _tiny_write(self, type_id: int, command: int, data=None):
    """
    writes data to tiny_block via I2C
    @param type_id: block type id
    @param command: one byte command
    @param data: specify input data for entered command
    """
    if self._check_type(type_id):
      self._raw_tiny_write(type_id, command, data)
    else:
      self.logging.error("invalid block type - writing interupted")

  def _tiny_read(self, type_id: int, command: int, in_data: bytes=None, expected_length: int=0):
    """
    reads data form tiny_block via I2C
    @param type_id: block type id
    @param command: one byte command
    @param in_data: specify input data for entered command
    @param expected_length: if defined will be read entered number of bytes. If None is expected length as a first byte
    @return provided bytes. If size is first byte is not included to output data
    """
    if self._check_type(type_id):
      self._raw_tiny_write(type_id, command, in_data)
      try:
        return self.i2c.readfrom(self.address, expected_length, True)
      except OSError:
        self.logging.error("tiny-block with address 0x%02X is unavailable for reading", self.address)
      return None
    else:
      self.logging.error("invalid block type - reading interupted")
      return None

  def change_block_address(self, new_address):
    self._tiny_write(
      self.i2c_block_type_id_base, self.change_i2c_address_command, new_address.to_bytes(1, 'big')
    )
    self.address = new_address
    time.sleep(0.1) #wait to the change is performed and stopped

  def _get_block_version(self):
    """
    returns block_type, pcb version, adjustment_version
    """
    data = self._tiny_read(
      self.i2c_block_type_id_base, self.get_module_version_command, None, 3
    )
    return (data[0], data[1], data[2])