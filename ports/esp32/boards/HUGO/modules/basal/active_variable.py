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
  def __init__(self, initial_value=None, renew_period:float=0, renew_func=None, ignore_same=True, change_threshold=None):
    """
    @param initial_value: if it is set the Active variable will be preset to this value.
      if the default value is set to None value call function will not be called in after
      the first update although the condition is met
    @param renew_period: renew_func will be called with this period if this value > 0
    @param renew_func: this method will be called periodically if renew_period is > 0 or
      if get is called with the parameter "force"
    @param ignore_same: does not call listener function when value does not change although the condition is met".
      Value updated listener is executed anyway.
    @param change_threshold: if a change listener is defined the threshold will be added to its comparison.
      If diference is smaller that the deffined threshold the assigned function will not be called.
      the condition is new_value <= last_value - threshold or new_value >= last_value + threshold.
      The threshold function will be applied to numbers only.
      If value is a collection the the threshold function will be applied to its number items.
      Last value is stored when the condition is met.
    """

    self._old_value = initial_value
    self._value = initial_value
    self._renew_period = renew_period
    self._renew_func = renew_func
    self._ignore_same = ignore_same
    self._change_threshold = change_threshold
    self._last_change_value = initial_value
    self._renew_handle = None
    self._listeners = list()
    self._handle_count = 0

  def set_ignore_same(self, ignore):
    self._ignore_same = ignore

  def set_change_threshold(self, threshold):
    self._change_threshold = threshold

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

    same = False
    if self._ignore_same:
      if isinstance(self._value, float) and isinstance(value, float):
        if math.isclose(self._value, value):
          same = True
      else:
        if self._value == value:
          same = True

    self._old_value = self._value
    self._value = value

    update_last_change_value = False
    for listener in self._listeners:
      _type = listener[1]
      repeat = listener[2]
      if _type == Conditions.value_updated:
        if  not repeat:
          self._remove_listener(listener)
        listener[3](*listener[4], **listener[5])
      elif not same:
        if _type == Conditions.equal_to:
          if self._is_equal(value, listener[3]):
            if  not repeat:
              self._remove_listener(listener) #TODO: maybe it can be returned to the end of this method it should not be important for the called methd that it will be removed later - events are synchronous
            listener[4](*listener[5], **listener[6])
        elif _type == Conditions.not_equal_to:
          if not self._is_equal(value, listener[3]):
            if  not repeat:
              self._remove_listener(listener)
            listener[4](*listener[5], **listener[6])
        elif _type == Conditions.less_than:
          if value < listener[3]:
            if  not repeat:
              self._remove_listener(listener)
            listener[4](*listener[5], **listener[6])
        elif _type == Conditions.more_than:
          if value > listener[3]:
            if  not repeat:
              self._remove_listener(listener)
            listener[4](*listener[5], **listener[6])
        elif _type == Conditions.in_range:
          if value >= listener[3] and value < listener[4]:
            if  not repeat:
              self._remove_listener(listener)
            listener[5](*listener[6], **listener[7])
        elif _type == Conditions.out_of_range:
          if value < listener[3] or value >= listener[4]:
            if  not repeat:
              self._remove_listener(listener)
            listener[5](*listener[6], **listener[7])
        elif _type == Conditions.value_changed:
          if self._last_change_value is None:
            self._last_change_value = value #to be functioin called only in case of a change
          if self._changed_with_threshold_complex(value):
            update_last_change_value = True #last value is changed indirectly another change listener can be present
            if  not repeat:
              self._remove_listener(listener)
            listener[3](*listener[4], **listener[5])
        else:
          self.logging.error("unknown listener type %s" % str(listener[1]))
    if update_last_change_value:
      self._last_change_value = value;

  def _is_equal(self, first, second):
     if isinstance(first, float) or isinstance(second, float):
        return math.isclose(first,second)
     return first == second


  def _changed_with_threshold_simple(self, value, last_value):
    if last_value is None or self._change_threshold is None:
      return True

    if not isinstance(value, (float, int)):
      return not self._is_equal(last_value, value)

    if not isinstance(last_value, (float, int)):
      return not self._is_equal(last_value, value)

    return value >= last_value + self._change_threshold or value <= last_value - self._change_threshold

  def _changed_with_threshold_complex(self, value):
    if isinstance(value, (tuple, list)) and isinstance(self._last_change_value, (tuple, list)) and len(value) == len(self._last_change_value):
      for index in range(0, len(value)):
        if self._changed_with_threshold_simple(value[index], self._last_change_value[index]):
          return True
      return False
    elif isinstance(value, dict) and isinstance(self._last_change_value, dict) and value.keys() == self._last_change_value.keys():
      for key, value in value.items():
        if self._changed_with_threshold_simple(value, self._last_change_value[key]):
          return True

      return False
    else:
      return self._changed_with_threshold_simple(value, self._last_change_value)

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

  def  remove_all_triggers(self):
    for listener in self._listeners:
      self._listeners.remove(listener)

    Planner.kill_task(self._renew_handle)
    self._renew_handle = None

  def _remove_listener(self, listener):
    return self.remove_trigger(listener[0])

  def equal_to(self, expected, function: callable, *args, **kwargs):
    """
    provided function with arguments will be called when
    measured value is equal to the expected value
    provided function will be called repeatedly until returned listener is not removed
    @returns plan handle
    """
    return self._add_listener((self._handle_count, Conditions.equal_to, True, expected, function, args, kwargs))

  def equal_to_once(self, expected, function: callable, *args, **kwargs):
    """
    provided function with arguments will be called when
    measured value is equal to the expected value
    provided function will be called only once
    @returns plan handle
    """
    return self._add_listener((self._handle_count, Conditions.equal_to, False, expected, function, args, kwargs))


  def not_equal_to(self, expected, function: callable, *args, **kwargs):
    """
    provided function with arguments will be called when
    measured value is not equal to the expected value
    provided function will be called repeatedly until returned listener is not removed
    @returns plan handle
    """
    return self._add_listener((self._handle_count, Conditions.not_equal_to, True, expected, function, args, kwargs))

  def not_equal_to_once(self, expected, function: callable, *args, **kwargs):
    """
    provided function with arguments will be called when
    measured value is not equal to the expected value
    provided function will be called only once
    @returns plan handle
    """
    return self._add_listener((self._handle_count, Conditions.not_equal_to, False, expected, function, args, kwargs))


  def less_than(self, expected, function: callable, *args, **kwargs):
    """
    provided function with arguments will be called when
    measured value is smaller than the expected value
    provided function will be called only repeatedly until returned listener is not removed
    @returns plan handle
    """
    return self._add_listener((self._handle_count, Conditions.less_than, True, expected, function, args, kwargs))

  def less_than_once(self, expected, function: callable, *args, **kwargs):
    """
    provided function with arguments will be called when
    measured value is smaller than the expected value
    provided function will be called only once
    @returns plan handle
    """
    return self._add_listener((self._handle_count, Conditions.less_than, False, expected, function, args, kwargs))


  def more_than(self, expected, function: callable, *args, **kwargs):
    """
    provided function with arguments will be called when
    measured value is bigger than the expected value
    provided function will be called only repeatedly until returned listener is not removed
    @returns plan handle
    """
    return self._add_listener((self._handle_count, Conditions.more_than, True, expected, function, args, kwargs))

  def more_than_once(self, expected, function: callable, *args, **kwargs):
    """
    provided function with arguments will be called when
    measured value is bigger than the expected value
    provided function will be called only once
    @returns plan handle
    """
    return self._add_listener((self._handle_count, Conditions.more_than, False, expected, function, args, kwargs))


  def in_range(self, expected_begin, expected_end, function: callable, *args, **kwargs):
    """
    provided function with arguments will be called when
    measured value is bigger or equal to the expected_begin value and smaller that the expected_end value
    provided function will be called only repeatedly until returned listener is not removed
    @returns plan handle
    """
    return self._add_listener((self._handle_count, Conditions.in_range, True, expected_begin, expected_end, function, args, kwargs))

  def in_range_once(self, expected_begin, expected_end, function: callable, *args, **kwargs):
    """
    provided function with arguments will be called when
    measured value is bigger or equal to the expected_begin value and smaller that the expected_end value
    provided function will be called only once
    @returns plan handle
    """
    return self._add_listener((self._handle_count, Conditions.in_range, False, expected_begin, expected_end, function, args, kwargs))


  def out_of_range(self, expected_begin, expected_end, function: callable, *args, **kwargs):
    """
    provided function with arguments will be called when
    measured value is smaller than the expected_begin value or bigger or equal to the expected_end value
    provided function will be called only repeatedly until returned listener is not removed
    @returns plan handle
    """
    return self._add_listener((self._handle_count, Conditions.out_of_range, True, expected_begin, expected_end, function, args, kwargs))

  def out_of_range_once(self, expected_begin, expected_end, function: callable, *args, **kwargs):
    """
    provided function with arguments will be called when
    measured value is smaller than the expected_begin value or bigger or equal to the expected_end value
    provided function will be called only once
    @returns plan handle
    """
    return self._add_listener((self._handle_count, Conditions.out_of_range, False, expected_begin, expected_end, function, args, kwargs))

  def changed(self, function: callable, *args, **kwargs):
    """
    provided function with arguments will be called when
    measured value is different than last time measured value
    provided function will be called only repeatedly until returned listener is not removed
    @returns plan handle
    """
    return self._add_listener((self._handle_count, Conditions.value_changed, True, function, args, kwargs))

  def changed_once(self, function: callable, *args, **kwargs):
    """
    provided function with arguments will be called when
    measured value is different than last time measured value
    provided function will be called only once
    @returns plan handle
    """
    return self._add_listener((self._handle_count, Conditions.value_changed, False, function, args, kwargs))


  def updated(self, function: callable, *args, **kwargs):
    """
    provided function with arguments will be called always when
    a value is updated (when it is measured)
    provided function will be called only repeatedly until returned listener is not removed
    @returns plan handle
    """
    return self._add_listener((self._handle_count, Conditions.value_updated, True, function, args, kwargs))

  def updated_once(self, function: callable, *args, **kwargs):
    """
    provided function with arguments will be called always when
    a value is updated (when it is measured)
    provided function will be called only once
    @returns plan handle
    """
    return self._add_listener((self._handle_count, Conditions.value_updated, False, function, args, kwargs))

  def __str__(self):
    return str(self.get())
