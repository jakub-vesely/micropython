#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

import basal.ble_ids as ble_ids
from basal.active_variable import ActiveVariable
from basal.logging import Logging
from basal.planner import Planner
class RemoteValue():
  remoteIds = {}

  @classmethod
  def _info(cls, message_id:str, activeVariable:ActiveVariable):
    Logging(message_id).value(str(activeVariable))

  @classmethod
  def add(cls, remote_id:str, active_variable:ActiveVariable):
    if remote_id in cls.remoteIds:
      return False

    cls.remoteIds[remote_id] = (active_variable, active_variable.updated(RemoteValue._info, remote_id, active_variable))
    return True

  @classmethod
  def _get_all(cls):
    for remote_id, value in cls.remoteIds.items():
      cls._info(remote_id, value[0])

  @classmethod
  def command_request(cls, command, data):
    if command == ble_ids.cmd_remote_val_get_all:
      Planner.plan(cls._get_all)
      return ble_ids.b_true
    return ble_ids.b_false

