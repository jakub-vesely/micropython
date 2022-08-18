#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

import os
import hashlib
from basal.logging import Logging
from blocks.main_block import MainBlock
from basal.planner import Planner
from basal.ble_ids import CommandId

#pyright: reportMissingImports=false
#pylint: disable=no-name-in-module ;implemented in micropython

class Shell():
  _b_false = b"\0"
  _b_true = b"\1"

  events_file_name = "events.mpy"
  import_error_file_name = ".import_error"

  def __init__(self) -> None:
    self.file_path = None
    self.new_file = False
    self.path = [""]
    self.dir_contents = list()
    self.dir_positions = list()
    self.logging = Logging("Shell")

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
    MainBlock.reboot()

  def _import_events(self):
    try:
      import events #events will planned
      self.logging.info("events loaded successfully")
      return True
    except Exception as error:
      self.logging.exception(error, extra_message="events.py was not imported properly")
      import sys
      sys.print_exception(error, sys.stdout)
      return False

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
    sha1 = hashlib.sha1(b"")
    with open(file_path, "rb") as file:
      while True:
        chunk = file.read(1000)
        if not chunk:
          break
        sha1.update(chunk)
    return sha1.digest()

  def _get_path(self):
    path = ""
    for item in self.path:
      path += item + "/"
    return path

  def _is_file(self, path):
    try:
      f = open(path, "r")
      f.close()
      return True
    except OSError:
      return False


  def _get_next_file_info(self):
    path = self._get_path()
    if len(self.dir_contents) < len(self.path):
      self.dir_contents.append(os.listdir(path))
      self.dir_positions.append(0)

    if self.dir_positions[-1] >= len(self.dir_contents[-1]):
      if len(self.dir_positions) > 1:
        self.dir_contents = self.dir_contents[:-1]
        self.dir_positions = self.dir_positions[:-1]
        self.path = self.path[:-1]
        return self._get_next_file_info()
      else:
        return self._b_false #proceses last file of root directory

    name = self.dir_contents[-1][self.dir_positions[-1]]
    file_path = path + name

    self.dir_positions[-1] += 1
    if self._is_file(file_path):
      return self._get_file_checksum(file_path) + file_path.encode("utf-8")
    else:
      self.path.append(name)
      return self._get_next_file_info()

  def command_request(self, command, data):
    if command == CommandId.common_version:
      return self._b_true

    elif command == CommandId.shell_stop_program:
      print("cmd_stop_program")
      if self.file_exists(self.events_file_name):
        print("events_file will be renamed")
        self.rename_file(self.events_file_name, "." + self.events_file_name)
        print("events_file renamed")
      print("reboot planned")
      Planner.postpone(0.1, self._reboot)
      return self._b_true

    elif command == CommandId.shell_start_program:
      return self._b_true if self._import_events() else self._b_false

    elif command == CommandId.shell_get_next_file_info:
      return self._get_next_file_info()

    elif command == CommandId.shell_remove_file:
      self.remove_file(data)
      return self._b_true

    elif command == CommandId.shell_handle_file:
      self.handeled_file_path = data
      self.new_file = True
      return self._b_true

    elif command == CommandId.shell_get_file_checksum:
      return self._get_file_checksum(self.handeled_file_path)

    elif command == CommandId.shell_append:
      if self.new_file:
        #print("path:" + str(self.handeled_file_path))
        file = open(self.handeled_file_path, "wb")
        self.new_file = False
      else:
        file = open(self.handeled_file_path, "ab")

      file.write(data)
      file.close()
      return self._b_true

    elif command == CommandId.shell_mk_dir:
      try:
        #print("mkdir..." + path.decode("utf-8"))
        os.mkdir(data)
        #print("mkdir Done")
      except Exception:
        #print("mkdir dir exists")
        return self._b_false
      return self._b_true

    else:
      return None
