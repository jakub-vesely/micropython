#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

from basal.active_variable import ActiveVariable
from remote_control.remote_key import RemoteKey
class RemoteCollector:
  def __init__(self):
    self.value = ActiveVariable(RemoteKey.get_default())

  def add_remote_active_varable(self, variable:ActiveVariable):
    variable.updated(self._update_value, variable)

  def _update_value(self, active_variable:ActiveVariable):
    self.value.set(active_variable.get())
