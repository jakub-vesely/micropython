#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

from planner import Planner
from logging import Logging
class SpecialKeys:
  left = "left"
  right = "right"
  top = "top"
  bottom = "bottom"
  space = "space"
  delete = "delete"
  backspace = "backspace"
  enter = "enter"
  page_up = "page up"
  page_down = "page down"
  home = "home"
  end = "end"
  ctrl = "ctrl"
  right_ctrl = "right ctrl"
  alt = "alt"
  right_alt = "right alt"
  window = "left windows"
  menu = "menu"
  caps_lock = "caps lock"
  tab = "tab"
  shift = "shift"
  right_shift = "right_shift"
  insert = "insert"
  pause = "pause"

class KeyCallback:
  def __init__(self, trigger, callback_type, *args, **kwargs) -> None:
    self.trigger = trigger
    self.callback_type = callback_type
    self.args = args
    self.kwargs = kwargs

logging = Logging("vk")

class VirtualKeyboard():
  callbacks = []

  @classmethod
  def process_input(cls, key_name:str = None, scan_code:bytes = None):
    logging.info("key:%s", key_name)
    for callback in cls.callbacks:
      if callback.trigger in (key_name, scan_code):
        Planner.plan(callback.callback_type, *callback.args, **callback.kwargs)

  @classmethod
  def add_callback(cls, trigger: callable, callback_type, *args, **kwargs):
    """
    trigger can be "key name" as string or "scan code" as integer
    """
    cls.callbacks.append(KeyCallback(trigger, callback_type, *args, **kwargs))

  @classmethod
  def del_callback(cls, trigger, callback_type):
    for callback in cls.callbacks:
      if callback.trigger == trigger and callback.callback_type == callback_type:
        cls.callbacks.remove(callback)
