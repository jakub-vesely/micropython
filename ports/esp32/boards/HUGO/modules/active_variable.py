import planner
from logging import Logging

class Conditions():
  equal_to = 1
  less_than = 2
  more_than = 3
  in_range = 4
  out_of_range = 5
  value_changed = 6

class ActiveVariable():
  logging = Logging("act_var")
  def __init__(self, initial_value, renew_period=0, renew_method=None):
    self._value = initial_value
    self._renew_period = renew_period
    self._renew_method = renew_method
    self._renew_handle = None
    self._listeners = list()
    self._handle_count = 0

  def change_period(self, new_period):
    self._renew_period = new_period
    if self._renew_handle:
      planner.kill(self._renew_handle)
    self._renew_handle = planner.repeat(self._renew_period, self._update_value)

  def set_value(self, value):
    old_value = self._value
    self._value = value
    for listener in self._listeners:
      processed = True
      _type = listener[1]
      repeat = listener[2]

      if _type == Conditions.equal_to:
        if value == listener[3]:
          listener[4](*listener[5], **listener[6])
      elif _type == Conditions.less_than:
        if value < listener[3]:
          listener[4](*listener[5], **listener[6])
      elif _type == Conditions.more_than:
        if value > listener[3]:
          listener[4](*listener[5], **listener[6])
      elif _type == Conditions.in_range:
        if value >= listener[3] and value <= listener[4]:
          listener[5](*listener[6], **listener[7])
      elif _type == Conditions.out_of_range:
        if value < listener[3] or value > listener[4]:
          listener[5](*listener[6], **listener[7])
      elif _type == Conditions.value_changed:
        if value != old_value:
          listener[3](*listener[4], **listener[5])
      else:
        self.logging.error("unknown listener type %s" % str(listener[1]))
        processed = False

      if processed and not repeat:
        self._listeners.remove(listener)

  def get_value(self, force=False):
    if not self._renew_handle or force:
      self._update_value()
    return self._value

  def _update_value(self):
    if self._renew_method:
      self.set_value(self._renew_method())

  def _add_listener(self, listener):
    if not self._listeners and self._renew_period:
      self._renew_handle = planner.repeat(self._renew_period, self._update_value)
    self._listeners.append(listener)
    self._handle_count += 1

  def remove_trigger(self, handle):
    for listener in self._listeners:
      if listener[0] == handle:
        self._listeners.remove(listener)
        if not self._listeners:
          planner.kill(self._renew_handle)
          self._renew_handle = None
        return True
    return False

  def equal_to_trigger(self, expected, repetitive, function, *args, **kwargs):
    self._add_listener((self._handle_count, Conditions.equal_to, expected, repetitive, function, args, kwargs))
    return self._handle_count

  def less_than_trigger(self, expected, repetitive, function, *args, **kwargs):
    self._add_listener((self._handle_count, Conditions.less_than, expected, repetitive, function, args, kwargs))
    return self._handle_count

  def more_than(self, expected, repetitive, function, *args, **kwargs):
    self._add_listener((self._handle_count, Conditions.more_than, expected, repetitive, function, args, kwargs))
    return self._handle_count

  def in_range(self, expected_min, expected_max, repetitive, function, *args, **kwargs):
    self._add_listener((self._handle_count, Conditions.in_range, expected_min, expected_max, repetitive, function, args, kwargs))
    return self._handle_count

  def out_of_range(self, expected_min, expected_max, repetitive, function, *args, **kwargs):
    self._add_listener((self._handle_count, Conditions.out_of_range, expected_min, expected_max, repetitive, function, args, kwargs))
    return self._handle_count

  def changed(self, repetitive, function, *args, **kwargs):
    self._add_listener((self._handle_count, Conditions.value_changed, repetitive, function, args, kwargs))
    return self._handle_count

