#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

class QuantityBase():
    """
    base class for quantity
    quantity is defined by name and units dictionary where keys are unit names and values are multipliers
    default
    """
    def __init__(self, name:str, units:dict, precision:int) -> None:
        self.name = name
        self.units = units
        self.precision = precision

    def _get_penalty(self, value):
        if value == 0:
            return 0

        abs_value = abs(value)
        if abs_value >= 1:
            for multiplier in range(1, 99): #just a number big enough
                if abs_value / float(pow(10, multiplier)) < 1:
                    remainder_mult = self._get_penalty(abs_value - int(abs_value)) / 10
                    remainder_mult += 1 if remainder_mult > 0 else 0  # 1 for dot
                    return multiplier + remainder_mult
        else:
            for multiplier in range(1, 99): #just a number big enough
                if abs_value * multiplier * 10 > 1:
                    return multiplier * 10
        return 1000 #just a big number

    def _get_basal_unit_name(self):
        for unit_name, multiplier in self.units.items():
            if multiplier == 1:
                return unit_name
        return ""

    def get_value_str(self, value, fit_size=0) -> str:
        if type(value) != int and type(value) != float:
            return str(value)

        last_penalty = 10000 #bigger than biggest penalty
        value_str = ""
        unit_str = ""
        basal_str = ""
        if value == 0:
            value_str = "0"
            unit_str = self._get_basal_unit_name()
        else:
            for unit_name, unit_multiplier in self.units.items():
                recalculated = float(value) / unit_multiplier
                new_penalty = self._get_penalty(recalculated)
                if new_penalty < last_penalty or unit_multiplier == 1:
                    new_value_str = ("{:.%dg}" % self.precision).format(recalculated)
                    if len(new_value_str) > 4 and  new_value_str[-4] == 'e' and new_value_str[-2] == '0':
                        #remove redundant zero to be string shorter
                        new_value_str = new_value_str[:-2] + new_value_str[-1]
                    if unit_multiplier == 1:
                        basal_str = new_value_str
                    if new_penalty < last_penalty:
                        last_penalty = new_penalty
                        value_str = new_value_str
                        unit_str = unit_name
        if fit_size != 0:
            if fit_size  < len(value_str) + len(unit_str) + 1:
                if fit_size  <= len(value_str) + len(unit_str):
                    final_str = value_str + unit_str #remove space
                elif basal_str and len(basal_str) <= fit_size:
                    final_str = basal_str #basal number without units
                else:
                    final_str = value_str[: fit_size - len(unit_str)] + unit_str #remove space and precision
            else:
                final_str = "{}{} {}".format(" " * (fit_size - (len(value_str) + len(unit_str) + 1)), value_str, unit_str)
        else:
            if "e" in value_str: #when string is in exponential notation is better to have it in basal unit
                final_str = basal_str + " " + self._get_basal_unit_name()
            else:
                final_str = value_str + " " + unit_str

        return final_str

    def get_full_str(self, value):
        return self.name + ": " + self.get_value_str(value)
