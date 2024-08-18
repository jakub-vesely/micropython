from basal.logging import LoggerBase

class SerialLogger(LoggerBase):
  critical_str = "C"
  error_str = "E"
  warning_str = "W"
  info_str = "I"
  debug_str = "D"

  @classmethod
  def log(cls, level, message):
    if level == cls.critical_id:
      level_str = cls.critical_str
    elif level == cls.error_id:
      level_str = cls.error_str
    elif level == cls.warning_id:
      level_str = cls.warning_str
    elif level == cls.info_id:
      level_str = cls.info_str
    elif level == cls.debug_id:
      level_str = cls.debug_str

    print("{0: <1} {1}".format(level_str, message.decode("utf-8")))