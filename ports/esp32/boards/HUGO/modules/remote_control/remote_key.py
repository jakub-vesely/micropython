#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

class RemoteKey:
  def __init__(self, name, scan_code=0, address=0):
    self.name = name
    self.scan_code = scan_code
    self.address = address

  def __eq__(self, second: object) -> bool:
    return second and self.name == second.name

  @staticmethod
  def get_default():
    return RemoteKey("", 0, 0)
