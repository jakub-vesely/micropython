#  Copyright (c) 2023 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

from basal.quantity_base import QuantityBase
class length(QuantityBase):
    def __init__(self, name: str="", precision: int=4, ) -> None:
        super().__init__(name if name else "v", {"km": 1e3, "m": 1, "cm": 1e-2, "mm": 1e-3, "um": 1e-6}, precision)
