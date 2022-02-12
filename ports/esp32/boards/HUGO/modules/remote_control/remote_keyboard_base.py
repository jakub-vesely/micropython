#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

class RemoteKeyboardBase:
  """
  this class is a base class for remote keyboards/controls (IR or the BLE one)
  example of usage can be found in examples/remote_control
  """

  def __init__(self, address_bit_tolerance=2) -> None:
    """
    The variable "address_bit_tolerance" is a workaround for quite common practice that address have 16 bits (not 8 + 8 inverted as is defined and used for data).
    Unfortunately it happens that the address is received malformed quite often. When there is define set of one or two RCs used for the project,
    addresses can be predefined and chosen if the received address is bitwise close (lower or equal to address_bit_distance).
    """
    self.address_bit_tolerance = address_bit_tolerance

  def get_address(self):
    raise NotImplementedError

  def find_name_by_scan_code(self, scan_code):
    raise NotImplementedError
