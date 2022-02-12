#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

import os
import hashlib
from logging import Logging
from main_block import MainBlock
from planner import Planner
from micropython import const

_cmd_version            = const(0x80)
_cmd_stop_program       = const(0x81)
_cmd_start_program      = const(0x82)
_cmd_get_next_file_info = const(0x83)
_cmd_remove_file        = const(0x84)
_cmd_handle_file        = const(0x85)
_cmd_get_file_checksum  = const(0x86)
_cmd_append             = const(0x87)
_cmd_mk_dir             = const(0x88)

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

  def command_request(self, data):
    if data and len(data) > 0:
      command = data[0]
      if command == _cmd_version:
        return self._b_true

      elif command == _cmd_stop_program:
        print("cmd_stop_program")
        if self.file_exists(self.events_file_name):
          print("events_file will be renamed")
          self.rename_file(self.events_file_name, "." + self.events_file_name)
          print("events_file renamed")
        print("reboot planned")
        Planner.postpone(0.1, self._reboot)
        return self._b_true

      elif command == _cmd_start_program:
        return self._b_true if self._import_events() else self._b_false

      elif command == _cmd_get_next_file_info:
        return self._get_next_file_info()

      elif command == _cmd_remove_file:
        file_path = data[1:]
        self.remove_file(file_path)
        return self._b_true

      elif command == _cmd_handle_file:
        self.handeled_file_path = data[1:]
        self.new_file = True
        return self._b_true

      elif command == _cmd_get_file_checksum:
        return self._get_file_checksum(self.handeled_file_path)

      elif command == _cmd_append:
        data = data[1:]
        if self.new_file:
          #print("path:" + str(self.handeled_file_path))
          file = open(self.handeled_file_path, "wb")
          self.new_file = False
        else:
          file = open(self.handeled_file_path, "ab")

        file.write(data)
        file.close()
        return self._b_true

      elif command == _cmd_mk_dir:
        path = data[1:]
        try:
          #print("mkdir..." + path.decode("utf-8"))
          os.mkdir(path)
          #print("mkdir Done")
        except Exception:
          #print("mkdir dir exists")
          return self._b_false
        return self._b_true

      else:
        return None
