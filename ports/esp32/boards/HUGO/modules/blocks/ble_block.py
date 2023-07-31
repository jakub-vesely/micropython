#  Copyright (c) 2023 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

import time
from blocks.block_types import BlockTypes
from blocks.block_base import BlockBase
from micropython import const   # type: ignore
from basal.planner import Planner

#from basal.active_variable import ActiveVariable
#from queue import Queue

# class RemoteVariable:
#   def __init__(self, remote_node_id:int, variable_id:int, active_variable:ActiveVariable):
#     self.remote_node_id = remote_node_id
#     self.variable_id = variable_id
#     self.active_variable = active_variable


class BleBlock(BlockBase):
  at_command_id = 0x01
  response_command_id = 0x02
  mesh_data_id = 0x03

  def __init__(self, address=None, measurement_period: float=0.1):
    super().__init__(BlockTypes.ble, address)   # type: ignore
    #self._response_queue = Queue()
    self.remote_variables = []
    #Planner.repeat(measurement_period, self.read_ble_message)

  def write_at_command(self, at_command:bytes):
    self._tiny_write(self.at_command_id, at_command)


  def _read_message(self, message_type, timeout):
    step = 0.01 #sec
    while (timeout >= 0):
      message = self._tiny_read(message_type, None, 0)
      if message:
        return message
      time.sleep(step if timeout > step else timeout)
      timeout -= step;
    return None

  def read_at_command_response(self, timeout=0):
    return self._read_message(self.response_command_id, timeout)

  def read_mesh_message(self, timeout=0):
    return self._read_message(self.mesh_data_id, timeout)


  def send_mesh_message(self, target_id:int, message:bytes):
    # it seems mesh with ack is not reliable +ACK=OK is sometimes not delivered when mesh message is
    # mesh without ack is used and mesh answer is expected
    # it seems that ACK is delivered reliably when mesh mesage is postponed 300ms that is quite a long time
    message = b"AT+MESH\x00" + target_id.to_bytes(2, "big") +  message + b"\x0d\x0a"
    self.write_at_command(message)
    resp = self.read_at_command_response(0.5)
    return resp == b'OK'
