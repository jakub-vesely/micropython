#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

from basal.quantity_base import QuantityBase
class Temperature(QuantityBase):
    def __init__(self, name: str="", precision: int=4, ) -> None:
        #TODO: drift for K and F + degree sign
        super().__init__(name if name else "T", {"°C": 1}, precision)
