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
        logging.error("unknown listener type %s" % str(listener[1]))
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

  def remove(self, handle):
    for listener in self._listeners:
      if listener[0] == handle:
        self._listeners.remove(listener)
        if not self._listeners:
          planner.kill(self._renew_handle)
          self._renew_handle = None
        return True
    return False

  def equal_to(self, expected, function, *args, **kwargs):
    self._add_listener((self._handle_count, Conditions.equal_to, False, expected, function, args, kwargs))

  def equal_to_repeat(self, expected, function, *args, **kwargs):
    self._add_listener((self._handle_count, Conditions.equal_to, True, expected, function, args, kwargs))

  def less_than(self, expected, function, *args, **kwargs):
    self._add_listener((self._handle_count, Conditions.less_than, False, expected, function, args, kwargs))

  def less_than_repeat(self, expected, function, *args, **kwargs):
    self._add_listener((self._handle_count, Conditions.less_than, True, expected, function, args, kwargs))

  def more_than(self, expected, function, *args, **kwargs):
    self._add_listener((self._handle_count, Conditions.more_than, False, expected, function, args, kwargs))

  def more_than_repeat(self, expected, function, *args, **kwargs):
    self._add_listener((self._handle_count, Conditions.more_than, True, expected, function, args, kwargs))

  def in_range(self, expected_min, expected_max, function, *args, **kwargs):
    self._add_listener((self._handle_count, Conditions.in_range, False, expected_min, expected_max, function, args, kwargs))

  def in_range_repeat(self, expected_min, expected_max, function, *args, **kwargs):
    self._add_listener((self._handle_count, Conditions.in_range, True, expected_min, expected_max, function, args, kwargs))

  def out_of_range(self, expected_min, expected_max, function, *args, **kwargs):
    self._add_listener((self._handle_count, Conditions.out_of_range, False, expected_min, expected_max, function, args, kwargs))

  def out_of_range_repeat(self, expected_min, expected_max, function, *args, **kwargs):
    self._add_listener((self._handle_count, Conditions.out_of_range, True, expected_min, expected_max, function, args, kwargs))

  def changed(self, function, *args, **kwargs):
    self._add_listener((self._handle_count, Conditions.value_changed, False, function, args, kwargs))

  def changed_repeat(self, function, *args, **kwargs):
    self._add_listener((self._handle_count, Conditions.value_changed, True, function, args, kwargs))

