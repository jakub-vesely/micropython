import machine

from ble import Ble
from logging import BleLogger, Logging
from shell import Shell
from planner import Planner

class MainBlock():
  planner = Planner()
  def __init__(self) -> None:
    self.shell = Shell(self)
    self.ble = Ble(self.shell.command_request)

    Logging().add_logger(BleLogger(self.planner, self.ble))

  def _reboot(self):
    machine.reset()

  def reboot(self):
    print("rebooting")
    self.ble.disconnect()
    self.planner.postpone(0.1, self._reboot)

  def run(self):
    self.shell.load_events()
    self.planner.run()
