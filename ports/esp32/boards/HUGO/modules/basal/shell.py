#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

import os
import hashlib
from basal.logging import Logging
from blocks.main_block import MainBlock
from basal.planner import Planner
import basal.ble_ids as ble_ids

#pyright: reportMissingImports=false
#pylint: disable=no-name-in-module ;implemented in micropython

class Shell():
  events_file_name = "events.mpy"
  do_not_import_file_name = ".do_not_import_import"

  file_path = None
  new_file = False
  path = [""]
  dir_contents = list()
  dir_positions = list()
  logging = Logging("Shell")
  events_imported = False

  @classmethod
  def file_exists(cls, path):
    try:
      file = open(path, "r")
      file.close()
      return True
    except OSError:  # open failed
      return False

  @classmethod
  def create_file(cls, file_path):
    with open(file_path, "w"):
      pass

  @classmethod
  def remove_file(cls, file_path):
    os.remove(file_path)

  @classmethod
  def rename_file(cls, orig_file_path, dest_file_path):
    os.rename(orig_file_path, dest_file_path)

  @classmethod
  def _reboot(cls):
    MainBlock.reboot()

  @classmethod
  def _import_events(cls):
    if not cls.file_exists(cls.events_file_name):
      print("events file not found")
      return False
    try:
      print("events will be imported")
      import events #events will planned
      cls.logging.info("events loaded successfully")
      cls.events_imported = True
      return True
    except Exception as error:
      cls.logging.exception(error, extra_message="events.py was not imported properly")
      import sys
      sys.print_exception(error, sys.stdout)
      return False

  @classmethod
  def load_events(cls):
    if cls.file_exists(cls.do_not_import_file_name):
      print("do_not_import_file_name removed")
      cls.remove_file(cls.do_not_import_file_name)
    else:
      cls._import_events()

  @classmethod
  def read_chunks(file, chunk_size):
    while True:
      data = file.read(chunk_size)
      if not data:
        break
      yield data

  @classmethod
  def _get_file_checksum(cls, file_path):
    sha1 = hashlib.sha1(b"")
    with open(file_path, "rb") as file:
      while True:
        chunk = file.read(1000)
        if not chunk:
          break
        sha1.update(chunk)
    return sha1.digest()

  @classmethod
  def _get_path(cls):
    path = ""
    for item in cls.path:
      path += item + "/"
    return path

  @classmethod
  def _is_file(cls, path):
    try:
      f = open(path, "r")
      f.close()
      return True
    except OSError:
      return False

  @classmethod
  def _get_next_file_info(cls):
    path = cls._get_path()
    if len(cls.dir_contents) < len(cls.path):
      cls.dir_contents.append(os.listdir(path))
      cls.dir_positions.append(0)

    if cls.dir_positions[-1] >= len(cls.dir_contents[-1]):
      if len(cls.dir_positions) > 1:
        cls.dir_contents = cls.dir_contents[:-1]
        cls.dir_positions = cls.dir_positions[:-1]
        cls.path = cls.path[:-1]
        return cls._get_next_file_info()
      else:
        return ble_ids.b_false #proceses last file of root directory

    name = cls.dir_contents[-1][cls.dir_positions[-1]]
    file_path = path + name

    cls.dir_positions[-1] += 1
    if cls._is_file(file_path):
      return cls._get_file_checksum(file_path) + file_path.encode("utf-8")
    else:
      cls.path.append(name)
      return cls._get_next_file_info()

  @classmethod
  def command_request(cls, command, data):
    if command == ble_ids.cmd_common_version:
      return ble_ids.b_true
    elif command == ble_ids.cmd_shell_program_started:
      return (ble_ids.b_true if cls.events_imported else ble_ids.b_false)
    elif command == ble_ids.cmd_shell_stop_program:
      print("cmd_stop_program")
      if data[0] == ble_ids.b_true and cls.file_exists(cls.events_file_name):
        print("do not import file will be created")
        cls.create_file(cls.do_not_import_file_name)

      print("reboot planned")
      Planner.postpone(0.1, cls._reboot)
      return ble_ids.b_true

    elif command == ble_ids.cmd_shell_start_program:
      return (ble_ids.b_true if cls._import_events() else ble_ids.b_false)

    elif command == ble_ids.cmd_shell_get_next_file_info:
      return cls._get_next_file_info()

    elif command == ble_ids.cmd_shell_remove_file:
      cls.remove_file(data)
      return ble_ids.b_true

    elif command == ble_ids.cmd_shell_handle_file:
      cls.handeled_file_path = data
      cls.new_file = True
      return ble_ids.b_true

    elif command == ble_ids.cmd_shell_get_file_checksum:
      return cls._get_file_checksum(cls.handeled_file_path)

    elif command == ble_ids.cmd_shell_append:
      if cls.new_file:
        file = open(cls.handeled_file_path, "wb")
        cls.new_file = False
      else:
        file = open(cls.handeled_file_path, "ab")

      file.write(data)
      file.close()
      return ble_ids.b_true

    elif command == ble_ids.cmd_shell_mk_dir:
      try:
        os.mkdir(data)
      except Exception:
        return ble_ids.b_false
      return ble_ids.b_true

    else:
      return None
