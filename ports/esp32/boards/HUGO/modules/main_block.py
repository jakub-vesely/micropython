import machine
import gc
import planner
from ble import Ble

ble = Ble()

def _reboot():
  machine.reset()

def reboot():
  print("rebooting")
  ble.disconnect()
  planner.postpone(0.1, _reboot)

def get_mem_info():
    free = gc.mem_free()
    allocated = gc.mem_alloc()
    total = free + allocated
    percent = "{0:.2f} %".format(free /  total * 100)
    return "Free mem: {0} ({1})".format(free, percent)

def run():
  ble.get_shell().load_events()
  planner.run()
  print("program terminated")
