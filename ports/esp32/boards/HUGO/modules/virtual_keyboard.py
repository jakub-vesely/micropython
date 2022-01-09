#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

from logging import Logging
from planner import Planner

class KeyCallback:
  def __init__(self, trigger, callback_method, *args, **kwargs) -> None:
    self.trigger = trigger
    self.callback_method = callback_method
    self.args = args
    self.kwargs = kwargs

class VirtualKeyboard():
  def __init__(self):
    self.logging = Logging("keybrd")
    self.callbacks = []

  def process_input(self, input):
    #self.logging.info("%s, %s", "keyboard_input1", input)
    scan_code = int.from_bytes(input[0:2], "big", True)
    key_name = input[2:].decode("utf-8")
    #self.logging.info("scan_code: %d, key_name: %s, %d", scan_code, key_name, len(self.callbacks))

    for callback in self.callbacks:
      #self.logging.info(str(("trigger:", callback.trigger, "key_name", key_name, callback.trigger == key_name)))
      if callback.trigger in (scan_code, key_name):
        Planner.plan(callback.callback_method, *callback.args, **callback.kwargs)

  def add_callback(self, trigger, callback_method, *args, **kwargs):
    """
    trigger can be "key name" as string or "scan code" as integer
    """
    self.callbacks.append(KeyCallback(trigger, callback_method, *args, **kwargs))

  def del_callback(self, trigger, callback_method):
    for callback in self.callbacks:
      if callback.trigger == trigger and callback.callback_method == callback_method:
        self.callbacks.remove(callback)
