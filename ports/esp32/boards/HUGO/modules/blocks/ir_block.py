#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

# pylint: disable=no-name-in-module
from micropython import const
from basal.active_variable import ActiveVariable
from blocks.block_types import BlockTypes
from blocks.block_base import BlockBase
from remote_control.remote_key import RemoteKey
from remote_control.remote_keyboard_base import RemoteKeyboardBase


_ir_data_ready_command = const(0x01)
_ir_data_command = const(0x02)

class IrBlock(BlockBase):
  _no_data_ready = RemoteKey.get_default()

  def __init__(self, address=None, measurement_period: float=0.1):
    BlockBase.__init__(self, BlockTypes.ir, address)
    self.value = ActiveVariable(RemoteKey.get_default(), measurement_period, self._get_value)
    self._remotes = list()

  def _get_value(self):
    ready = self._tiny_read(_ir_data_ready_command, None, 1)
    if ready and ready[0]:
      data = self._tiny_read(_ir_data_command, None, 4)
      hex_addr = ''.join(['{:02x}'.format(b) for b in data[0:2]])
      self.logging.debug("address ", hex_addr)
      raw_address = data[0] + (data[1] << 8)
      scan_code = data[2] #data[3] (repeat ) is not used yet
      remote = self._get_near_remote(raw_address)
      if remote:
        self.logging.info("scan_code:%d, raw_address:%d", scan_code, raw_address)
        return RemoteKey(remote.find_name_by_scan_code(scan_code), scan_code, remote.get_address())
    return self._no_data_ready #None is reserved for the case that block do not answer

  def add_remote(self, remote_control:RemoteKeyboardBase):
    self._remotes.append(remote_control)

  def _get_near_remote(self, received) -> RemoteKeyboardBase:
    for remote in self._remotes:
      address = remote.get_address()
      count = 0
      for index in range(16):
        if (address >> index) & 0x01 != (received >> index) & 0x01:
          count += 1
      if count <= remote.address_bit_tolerance:
        return remote
    return None
