#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT
from logging import Logging
from active_variable import ActiveVariable

class SmoothingType:
  average=0 #will be calculated average value from stored values
  progressive=1 #will be calculated weight average where oldest value have weight 1, second oldest 2, third oldest 3, etc.

class SmoothedVariable(ActiveVariable):
  def __init__(self, count:int, type:SmoothingType, active_variable:ActiveVariable = None):
    super().__init__(active_variable.get_value(False))
    self._active_variable = active_variable
    self._active_variable.updated(True, self._original_variable_updated)
    self._count = count
    self._type = type
    self._values = [active_variable._value] if active_variable._value is not None else []

  def _original_variable_updated(self):
    self.set_value(self._active_variable.get_value())

  def set_value(self, value):
    if len(self._values) >= self._count:
      del self._values[0]
    self._values.append(value)
    super().set_value(self.get_value(False))

  def get_value(self, force=False):
    if force:
      self._active_variable.get_value(force) #value will be added internally

    if not self._values:
      return None

    if len(self._values) == 1:
      return self._values[0]

    if self._type == SmoothingType.average:
      sum = 0
      for value in self._values:
        sum += value
      return sum / len(self._values)

    if self._type == SmoothingType.progressive:
      sum = 0
      factor = 0
      for index in range(len(self._values)):
        sum += self._values[index] * (index + 1)
        factor += index + 1
      return sum / factor

    return None
