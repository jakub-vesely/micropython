#  Copyright (c) 2023 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

from basal.quantity_base import QuantityBase
class Angle(QuantityBase):
    def __init__(self, name: str="", precision: int=4, ) -> None:
        super().__init__(name if name else "Ang", {"°": 1}, precision)
