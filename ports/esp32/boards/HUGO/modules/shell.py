import os
import hashlib

class Shell():
  _cmd_version               = 0x80
  _cmd_stop_program          = 0x81
  _cmd_start_program         = 0x82
  _cmd_get_next_file_info    = 0x83
  _cmd_remove_file           = 0x84
  _cmd_handle_file           = 0x85
  _cmd_get_file_checksum     = 0x86
  _cmd_append                = 0x87

  _b_false = b"\0"
  _b_true = b"\1"

  events_file_name = "events.py"

  def __init__(self, main_block) -> None:
    self.file_path = None
    self.new_file = False
    self.dir_content = None
    self.dir_pos = 0
    self.main_block = main_block

  def file_exists(self, path):
    try:
      file = open(path, "r")
      file.close()
      return True
    except OSError:  # open failed
      return False

  def remove_file(self, file_path):
    os.remove(file_path)

  def rename_file(self, orig_file_path, dest_file_path):
    os.rename(orig_file_path, dest_file_path)

  def _reboot(self):
    self.main_block.reboot()

  def _import_events(self):
    try:
      import events #events will planned
    except Exception as error:
      print("import events raised exception: ", error)
  def load_events(self):
    if self.file_exists(self.events_file_name):
      self._import_events()
    else:
      hidden_file_name = "." + self.events_file_name
      if self.file_exists(hidden_file_name): #if events.py has been hidden to do not be loaded, return them visible to be changed or used next time
        self.rename_file(hidden_file_name, self.events_file_name)

  def read_chunks(file, chunk_size):
    while True:
      data = file.read(chunk_size)
      if not data:
        break
      yield data

  def _get_file_checksum(self, file_path):
    sha1 = hashlib.sha1("")
    with open(file_path, "rb") as file:
      while True:
        chunk = file.read(1000)
        if not chunk:
          break
        sha1.update(chunk)
    return sha1.digest()

  def command_request(self, data):
    #print(("command_request", data))
    if data and len(data) > 0:
        command = data[0]
        if command == self._cmd_version:
          return self._b_true

        elif command == self._cmd_stop_program:
          if self.file_exists(self.events_file_name):
            self.rename_file(self.events_file_name, "." + self.events_file_name)
          self.main_block.planner.postpone(0.1, self._reboot)
          return self._b_true

        elif command == self._cmd_start_program:
          self._import_events()
          return self._b_true

        elif command == self._cmd_get_next_file_info:
          if not self.dir_content:
            self.dir_content = os.listdir("/")
          if self.dir_pos >= len(self.dir_content):
            return self._b_false
          name = self.dir_content[self.dir_pos]
          self.dir_pos += 1
          return self._get_file_checksum(name) + name.encode("utf-8")

        elif command == self._cmd_remove_file:
          filename = data[1:]
          self.remove_file(filename)
          return self._b_true

        elif command == self._cmd_handle_file:
          self.handeled_file_path = data[1:]
          self.new_file = True
          return self._b_true

        elif command == self._cmd_get_file_checksum:
          return self._get_file_checksum(self.handeled_file_path)

        elif command == self._cmd_append:
          data = data[1:]
          if self.new_file:
            file = open(self.handeled_file_path, "wb")
            self.new_file = False
          else:
            file = open(self.handeled_file_path, "ab")

          file.write(data)
          file.close()
          return self._b_true

        else:
          return None
