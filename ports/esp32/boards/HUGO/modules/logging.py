import sys
import os

#taken from https://docs.micropython.org/en/latest/reference/filesystem.html#hybrid-esp32
class RAMBlockDev:
  def __init__(self, block_size, num_blocks):
    self.block_size = block_size
    self.data = bytearray(block_size * num_blocks)

  def readblocks(self, block_num, buf):
    for i in range(len(buf)):
      buf[i] = self.data[block_num * self.block_size + i]

  def writeblocks(self, block_num, buf):
    for i in range(len(buf)):
      self.data[block_num * self.block_size + i] = buf[i]

  def ioctl(self, op, arg):
    if op == 4: # get number of blocks
      return len(self.data) // self.block_size
    if op == 5: # get block size
      return self.block_size

class LoggerBase():
  def log(self, message):
    raise NotImplementedError

class BleLogger():
  def __init__(self, planner, ble):
    self.planner = planner
    self.ble = ble
    #self.level = self.INFO

  def _log_to_ble(self, message):
    self.ble.notify_log(message)

  def log(self, message):
    self.planner.plan(self._log_to_ble, message)

class Logging():
  CRITICAL = 51
  ERROR    = 41
  WARNING  = 31
  INFO     = 21
  DEBUG    = 11
  NOTSET   = 0

  loggers = list()
  def __init__(self, tag=None):
    self.level = self.INFO
    self.tag = tag if tag else ""

    #TODO: block count - reduce size
    #ram_disk = RAMBlockDev(512, 5)
    #os.VfsFat.mkfs(ram_disk)
    #os.mount(ram_disk, '/ramdisk')

  @staticmethod
  def add_logger(logger):
    Logging.loggers.append(logger)

  def fit(self, msg_length, is_first):
    len_prefix = 3 + len(self.tag) if is_first else 0  # 2: level + ": "
    return  len_prefix + msg_length < 512 # < MP_BLUETOOTH_DEFAULT_ATTR_LEN ('\f' can be added)

  def log(self, level, message, *args, has_prefix=True):
    if level < self.level:
      return

    prefix = bytes([level]) + (self.tag + ": ").encode("utf-8") if has_prefix else b""
    complete = prefix + ((message % args) if args else message).encode("utf-8")
    for logger in self.loggers:
      logger.log(complete)

  def exception(self, exc, level=ERROR, extra_message=None):
    if level < self.level:
      return

    file_name = ".error"
    with open(file_name, "w") as file:
      sys.print_exception(exc, file)
    is_first = True
    with open(file_name, "r") as file:
      content = extra_message + "\n" if extra_message else ""
      while True:
        line = file.readline()
        if not line:
          break

        if not self.fit(len(content) + len(line), is_first):
          content += "\f" # add page separator indicating message continuation to the message reader
          self.log(level, content, has_prefix=is_first)
          content = ""
          is_first = False
        content += line
      if content:
        self.log(level, content, has_prefix=is_first)
    os.remove(file_name)

  def debug(self, msg, *args):
    self.log(self.DEBUG, msg, *args)

  def info(self, msg, *args):
    self.log(self.INFO, msg, *args)

  def warning(self, msg, *args):
    self.log(self.WARNING, msg, *args)

  def error(self, msg, *args):
    self.log(self.ERROR, msg, *args)

  def critical(self, msg, *args):
    self.log(self.CRITICAL, msg, *args)
