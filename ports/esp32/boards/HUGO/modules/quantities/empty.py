#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

from basal.quantity_base import QuantityBase
class Empty(QuantityBase):
    def __init__(self, name) -> None:
        super().__init__(name, {"", 1}, 0)
