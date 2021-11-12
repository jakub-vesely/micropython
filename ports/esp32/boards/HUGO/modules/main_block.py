import machine
import planner
from ble import Ble

ble = Ble()

def _reboot():
  machine.reset()

def reboot():
  print("rebooting")
  ble.disconnect()
  planner.postpone(0.1, _reboot)

def run():
  ble.get_shell().load_events()
  planner.run()
  print("program terminated")
