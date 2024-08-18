#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

from basal.quantity_base import QuantityBase
class Voltage(QuantityBase):
    def __init__(self, name: str="", precision: int=4) -> None:
        super().__init__(name if name else "U", {"kV": 1e3, "V": 1, "mV": 1e-3, "uV": 1e-6}, precision)
