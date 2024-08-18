#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

from basal.quantity_base import QuantityBase
class Pressure(QuantityBase):
    def __init__(self, name: str="", precision: int=4) -> None:
        super().__init__(name if name else "P", {"kPa": 1e3, "hPa": 1e2, "Pa": 1}, precision)
