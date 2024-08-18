#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

from basal.active_variable import ActiveVariable
from basal.quantity_base import QuantityBase

class ActiveQuantity(ActiveVariable):
    def __init__(self,
        quantity:QuantityBase,
        initial_value=None,
        renew_period:float=0,
        renew_func=None,
        ignore_same=True,
        change_threshold = None
    ):
        super().__init__(initial_value, renew_period, renew_func, ignore_same, change_threshold)
        self.quantity = quantity

    def __str__(self):
        return self.quantity.get_full_str(self.get())

    def get_str_to_fit(self, size):
        return self.quantity.get_value_str(self.get(), size)

    def get_name(self):
        return self.quantity.name

    def set_with_units(self, value, unit):
        multiplier = 1;
        if (unit in self.quantity.units):
            multiplier = self.quantity.units[unit]
        self.set(value * multiplier)
