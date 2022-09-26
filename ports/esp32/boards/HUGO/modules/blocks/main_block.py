#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

import machine
import gc
from basal.planner import Planner
from basal.ble import Ble

class MainBlock:
  @staticmethod
  def _reboot():
    machine.reset()

  @classmethod
  def reboot(cls):
    print("rebooting")
    Ble.disconnect()
    Planner.postpone(0.1, cls._reboot)

  @staticmethod
  def get_mem_info():
    free = gc.mem_free()
    allocated = gc.mem_alloc()
    total = free + allocated
    percent = "{0:.2f} %".format(free /  total * 100)
    return "Free mem: {0} ({1})".format(free, percent)

  @staticmethod
  def run():
    Ble.init()
    Ble.get_shell().load_events()
    Planner.run()

  @staticmethod
  def power_save() -> None:
    pass #TODO: is here anything to do?
