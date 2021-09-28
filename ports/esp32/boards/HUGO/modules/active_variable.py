class ActiveVariable():
  _equal_to = 1
  _less_than = 2
  _more_than = 3
  _in_range = 4
  _out_of_range = 5
  #_changed_less_than = 7
  #_changed_more_than = 8

  def __init__(self, value):
    self._value = value
    self.triggers = list()

  def set_value(self, value):
    self._value = value
    processed = True
    for trigger in self.triggers:
      _type = trigger[0]
      repeat = trigger[1]

      if _type == self._equal_to:
        if value == trigger[2]:
          trigger[3](*trigger[4], **trigger[5])
      elif _type == self._less_than:
        if value < trigger[2]:
          trigger[3](*trigger[4], **trigger[5])
      elif _type == self._more_than:
        if value > trigger[2]:
          trigger[3](*trigger[4], **trigger[5])
      elif _type == self._in_range:
        if value >= trigger[2] and value <= trigger[3]:
          trigger[4](*trigger[5], **trigger[6])
      elif _type == self._out_of_range:
        if value < trigger[2] or value > trigger[3]:
          trigger[4](*trigger[5], **trigger[6])
      else:
        print("unknown trigger type %s" % str(trigger[0]))
        processed = False

      if processed and not repeat:
        self.triggers.remove(trigger)

  def get_value(self):
    return self._value

  def equal_to_trigger(self, expected, function, *args, **kwargs):
     self.triggers.append((self._equal_to, False, expected, function, args, kwargs))

  def equal_to_repeat_trigger(self, expected, function, *args, **kwargs):
     self.triggers.append((self._equal_to, True, expected, function, args, kwargs))

  def less_than_trigger(self, expected, function, *args, **kwargs):
     self.triggers.append((self._less_than, False, expected, function, args, kwargs))

  def less_than_repeat_trigger(self, expected, function, *args, **kwargs):
     self.triggers.append((self._less_than, True, expected, function, args, kwargs))

  def more_than_trigger(self, expected, function, *args, **kwargs):
     self.triggers.append((self._more_than, False, expected, function, args, kwargs))

  def more_than_repeat_trigger(self, expected, function, *args, **kwargs):
     self.triggers.append((self._more_than, True, expected, function, args, kwargs))

  def in_range_trigger(self, expected_min, expected_max, function, *args, **kwargs):
     self.triggers.append((self._in_range, False, expected_min, expected_max, function, args, kwargs))

  def in_range_repeat_trigger(self, expected_min, expected_max, function, *args, **kwargs):
     self.triggers.append((self._in_range, True, expected_min, expected_max, function, args, kwargs))

  def out_of_range_trigger(self, expected_min, expected_max, function, *args, **kwargs):
     self.triggers.append((self._out_of_range, False, expected_min, expected_max, function, args, kwargs))

  def out_of_range_repeat_trigger(self, expected_min, expected_max, function, *args, **kwargs):
     self.triggers.append((self._out_of_range, True, expected_min, expected_max, function, args, kwargs))
