#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

from basal.quantity_base import QuantityBase
class Current(QuantityBase):
    def __init__(self, name: str="", precision: int=4) -> None:
        super().__init__(name if name else "I", {"kA": 1e3, "A": 1, "mA": 1e-3, "uA": 1e-6}, precision)
