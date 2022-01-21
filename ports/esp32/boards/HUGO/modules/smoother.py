#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

class SmoothingMethod:
  average=0 #will be calculated average value from stored values
  progressive=1 #will be calculated weight average where oldest value have weight 1, second oldest 2, third oldest 3, etc.

class Smoother:
  def __init__(self, count:int, method:SmoothingMethod):
    self._count = count
    self._method = method
    self._values = []

  def add(self, value):
    if len (self._values) > self._count:
      del self._values[0]
    self._values.append(value)

  def get(self):
    if not self._values:
      return None
    if len(self._values) == 1:
      return self._values[0]
    if self._method == SmoothingMethod.average:
      sum = 0
      for value in self._values:
        sum += value
      return sum / len(self._values)
    if self._method == SmoothingMethod.progressive:
      sum = 0
      factor = 0
      for index in range(len(self._values)):
        sum += self._values[index] * index + 1
        factor += index + 1
      return sum / factor
    return None