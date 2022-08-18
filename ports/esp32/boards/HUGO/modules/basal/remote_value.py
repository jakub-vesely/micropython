#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

from basal.ble_ids import RemoteValueId
from basal.ble import Ble
from basal.active_variable import ActiveVariable

class RemoteValue():
  remoteIds = {}
  @classmethod
  def _send(cls, message_id:int, message:bytes):
    Ble.notify_remote_value(message_id.to_bytes(1, 'big') + message)

  @classmethod
  def _info(cls, remote_id_bytes, activeVariable:ActiveVariable):
    cls._send(RemoteValueId.info, remote_id_bytes + b"\x01" + str(activeVariable).encode("utf-8"))

  @classmethod
  def add(cls, remote_id:str, active_variable:ActiveVariable):
    if remote_id in cls.remoteIds:
      return False
    remote_id_bytes = remote_id.encode("utf-8")
    cls.remoteIds[remote_id_bytes] = active_variable.changed(True, RemoteValue._info, remote_id_bytes, active_variable)
    cls._send(RemoteValueId.added, remote_id_bytes)
    return True
