#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

from basal.planner import Planner
from basal.logging import Logging
import math

class Conditions():
  equal_to = 1
  not_equal_to = 2
  less_than = 3
  more_than = 4
  in_range = 5
  out_of_range = 6
  value_changed = 7
  value_updated = 8

class ActiveVariable():
  logging = Logging("act_var")
  def __init__(self, initial_value=None, renew_period=0, renew_func=None):
    """
    @param initial_value: if is set Active variable will be preset to this value
    @param renew_period: renew_func will be called with this period if this value > 0
    @param renew_func: this method will be called periodically if renew_period is > 0 or if get is called with the parameter "force"
    """
    self._old_value = initial_value
    self._value = initial_value
    self._renew_period = renew_period
    self._renew_func = renew_func
    self._renew_handle = None
    self._listeners = list()
    self._handle_count = 0

  def change_period(self, new_period):
    self._renew_period = new_period
    if self._renew_handle:
      Planner.kill_task(self._renew_handle)
      self._renew_handle = None
    if self._renew_period > 0:
      self._renew_handle = Planner.repeat(self._renew_period, self._update_value)

  def set(self, value):
    if value is None:
      return #nothing to compare
    self._old_value = self._value
    self._value = value
    for listener in self._listeners:
      _type = listener[1]
      repeat = listener[2]

      if _type == Conditions.equal_to:
        if isinstance(value, float) or isinstance(listener[3], float):
          if (self._old_value is None or not math.isclose(self._old_value, listener[3])) and math.isclose(value, listener[3]):
            if  not repeat:
              self._remove_listener(listener) #TODO: maybe it can be returned to the end of this method it should not be important for the called methd that it will be removed later - events are synchronous
            listener[4](*listener[5], **listener[6])
        else:
          if (self._old_value is None or self._old_value != listener[3]) and value == listener[3]:
            if  not repeat:
              self._remove_listener(listener)
            listener[4](*listener[5], **listener[6])
      elif _type == Conditions.not_equal_to:
        if isinstance(value, float) or isinstance(listener[3], float):
          if (self._old_value is None or math.isclose(self._old_value, listener[3])) and not math.isclose(value, listener[3]):
            if  not repeat:
              self._remove_listener(listener)
            listener[4](*listener[5], **listener[6])
        else:
          if (self._old_value is None or self._old_value == listener[3]) and value != listener[3]:
            if  not repeat:
              self._remove_listener(listener)
            listener[4](*listener[5], **listener[6])
      elif _type == Conditions.less_than:
        if (self._old_value is None or self._old_value >= listener[3]) and value < listener[3]:
          if  not repeat:
            self._remove_listener(listener)
          listener[4](*listener[5], **listener[6])
      elif _type == Conditions.more_than:
        if (self._old_value is None or self._old_value <= listener[3]) and value > listener[3]:
          if  not repeat:
            self._remove_listener(listener)
          listener[4](*listener[5], **listener[6])
      elif _type == Conditions.in_range:
        if (self._old_value is None or self._old_value < listener[3] or self._old_value >= listener[4]) and  value >= listener[3] and value < listener[4]:
          if  not repeat:
            self._remove_listener(listener)
          listener[5](*listener[6], **listener[7])
      elif _type == Conditions.out_of_range:
        if (self._old_value is None or self._old_value >= listener[3] and self._old_value < listener[4]) and (value < listener[3] or value >= listener[4]):
          if  not repeat:
            self._remove_listener(listener)
          listener[5](*listener[6], **listener[7])
      elif _type == Conditions.value_changed:
        if value != self._old_value:
          if  not repeat:
            self._remove_listener(listener)
          listener[3](*listener[4], **listener[5])
      elif _type == Conditions.value_updated:
        if  not repeat:
          self._remove_listener(listener)
        listener[3](*listener[4], **listener[5])
      else:
        self.logging.error("unknown listener type %s" % str(listener[1]))

  def get(self, force=False):
    if force:
      self._update_value()
    return self._value

  def get_previous_value(self):
    return self._old_value

  def _update_value(self):
    if self._renew_func:
      self.set(self._renew_func())

  def _add_listener(self, listener):
    if not self._listeners and self._renew_period > 0:
      self._renew_handle = Planner.repeat(self._renew_period, self._update_value)
    self._listeners.append(listener)
    self._handle_count += 1
    return listener[0] #returns provided handle

  def remove_trigger(self, handle):
    for listener in self._listeners:
      if listener[0] == handle:
        self._listeners.remove(listener)
        if not self._listeners:
          Planner.kill_task(self._renew_handle)
          self._renew_handle = None
        return True
    return False

  def _remove_listener(self, listener):
    return self.remove_trigger(listener[0])

  def equal_to(self, expected, repetitive: bool, function: callable, *args, **kwargs):
    """
    provided function with arguments will be called when
    measured value is newly equal to expected value
    """
    return self._add_listener((self._handle_count, Conditions.equal_to, repetitive, expected, function, args, kwargs))

  def not_equal_to(self, expected, repetitive: bool, function: callable, *args, **kwargs):
    """
    provided function with arguments will be called when
    measured value is newly not equal to expected value
    """
    return self._add_listener((self._handle_count, Conditions.not_equal_to, repetitive, expected, function, args, kwargs))


  def less_than(self, expected, repetitive: bool, function: callable, *args, **kwargs):
    """
    provided function with arguments will be called when
    measured value is newly smaller than expected value
    """
    return self._add_listener((self._handle_count, Conditions.less_than, repetitive, expected, function, args, kwargs))

  def more_than(self, expected, repetitive:bool, function: callable, *args, **kwargs):
    """
    provided function with arguments will be called when
    measured value is newly bigger than expected value
    """
    return self._add_listener((self._handle_count, Conditions.more_than, repetitive, expected, function, args, kwargs))

  def in_range(self, expected_min, expected_max, repetitive: bool, function: callable, *args, **kwargs):
    """
    provided function with arguments will be called when
    measured value is newly bigger or equal to expected_min value and smaller that expected_max value
    """
    return self._add_listener((self._handle_count, Conditions.in_range, repetitive, expected_min, expected_max, function, args, kwargs))

  def out_of_range(self, expected_min, expected_max, repetitive: bool, function: callable, *args, **kwargs):
    """
    provided function with arguments will be called when
    measured value is newly smaller than expected_min value or bigger or equal to expected_max value
    """
    return self._add_listener((self._handle_count, Conditions.out_of_range, repetitive, expected_min, expected_max, function, args, kwargs))

  def changed(self, repetitive: bool, function: callable, *args, **kwargs):
    """
    provided function with arguments will be called when
    measured value is different that last time measured value
    """
    return self._add_listener((self._handle_count, Conditions.value_changed, repetitive, function, args, kwargs))

  def updated(self, repetitive: bool, function: callable, *args, **kwargs):
    """
    provided function with arguments will be called always when
    a value is measured
    """
    return self._add_listener((self._handle_count, Conditions.value_updated, repetitive, function, args, kwargs))
