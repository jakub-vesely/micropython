#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

from remote_control.remote_keyboard_base import RemoteKeyboardBase
from remote_control.special_keys import SpecialKeys
from remote_control.remote_key import RemoteKey

class IrNumericRemote(RemoteKeyboardBase):
  """
  this class describes a cheap remote control with a numeric keyboard and a navigation cross
  """
  address = 65280

  key_1 = RemoteKey("1", 69, address)
  key_2 = RemoteKey("2", 70, address)
  key_3 = RemoteKey("3", 71, address)
  key_4 = RemoteKey("4", 68, address)
  key_5 = RemoteKey("5", 64, address)
  key_6 = RemoteKey("6", 67, address)
  key_7 = RemoteKey("7", 7, address)
  key_8 = RemoteKey("8", 21, address)
  key_9 = RemoteKey("9", 9, address)
  key_0 = RemoteKey("0", 25, address)
  key_star = RemoteKey("*", 22, address)
  key_hash = RemoteKey("#", 13, address)
  key_ok = RemoteKey(SpecialKeys.ok, 28, address)
  key_left = RemoteKey(SpecialKeys.left, 8, address)
  key_right = RemoteKey(SpecialKeys.right, 90, address)
  key_up = RemoteKey(SpecialKeys.up, 24, address)
  key_down = RemoteKey(SpecialKeys.down, 82, address)

  _keys = (
      key_1,
      key_2,
      key_3,
      key_4,
      key_5,
      key_6,
      key_7,
      key_8,
      key_9,
      key_0,
      key_star,
      key_hash,
      key_ok,
      key_left,
      key_right,
      key_up,
      key_down,
  )

  def get_address(self):
    return self.address

  def find_name_by_scan_code(self, scan_code):
    for key in self._keys:
      if key.scan_code == scan_code:
        return key.name
    return None



