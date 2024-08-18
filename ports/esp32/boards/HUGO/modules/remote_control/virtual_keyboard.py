#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

from remote_control.remote_keyboard_base import RemoteKeyboardBase

class KeyCallback:
  def __init__(self, trigger, callback_type, *args, **kwargs) -> None:
    self.trigger = trigger
    self.callback_type = callback_type
    self.args = args
    self.kwargs = kwargs

class VirtualKeyboard(RemoteKeyboardBase):
  def get_address(self):
    return 1 #a number

  def find_name_by_scan_code(self, scan_code):
    return None #key objects are not stored statically, get_object_from_scancode (parent's method) will not provide any objects

