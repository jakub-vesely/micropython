#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

from blocks.block_types import BlockTypes
from blocks.block_base import BlockBase
from basal.active_variable import ActiveVariable
from micropython import const
import time

_i2c_wt_chip_command  = const(0x01)
_i2c_wt_chip_response = const(0x02)

_play_by_root_index_command_id      = const(0xa2)
_play_by_root_name_command_id       = const(0xa3)
_play_by_folder_index_command_id    = const(0xa4)
_play_by_folder_name_command_id     = const(0xa5)
_play_pause_command_id              = const(0xaa)
_stop_command_id                    = const(0xab)
_play_next_command_id               = const(0xac)
_play_previous_command_id           = const(0xad)
_volume_command_id                  = const(0xae)
_mode_command_id                    = const(0xaf)
_combination_play_command_id        = const(0xb1)
_inter_cut_play_command_id          = const(0xb1)
_eq_mode_command_id                 = const(0xb2)
_end_code_command_id                = const(0xba)
_get_volume_command_id              = const(0xc1)
_get_status_command_id              = const(0xc2)
_get_track_count_command_id         = const(0xc5)
_get_folder_track_count_command_id  = const(0xc6)
_get_track_index_command_id         = const(0xc9)
_get_devices_command_id             = const(0xca)
_get_track_name_command_id          = const(0xcb)
_switch_to_work_drive               = const(0x0d)

_max_volume = const(0x1F) #31
_min_volume = const(0x00)

class PlayMode:
  single_play =         0x00
  single_loop_play =    0x01
  all_track_loop_play = 0x02
  random_playing =      0x03

class EqMode:
  normal =    0x00
  pop =       0x01
  rock =      0x02
  jazz =      0x03
  classinc =  0x04
  base =      0x05

class Status:
  play =  0x01
  stop =  0x02
  pause = 0x03

class SoundBlock(BlockBase):

  def __init__(self, address=None):
    super().__init__(BlockTypes.sound, address)
    self.set_play_mode(PlayMode.single_play) #it is not possible to get current mode I will reset the mode set after power-off
    self._play_mode = PlayMode.single_play

    self.set_eq_mode(EqMode.normal)
    self._eq_mode = EqMode.normal

  def _wt_chip_command(self, command_id: int, payload:bytes=None):
    data = command_id.to_bytes(1, "big")
    if payload:
      data += payload
    #self.logging.info("sent %s", str(data))
    self._tiny_write(_i2c_wt_chip_command, data)

  def _wt_chip_response(self, expected_size:int):
    data = self._tiny_read(_i2c_wt_chip_response, None, expected_size)
    #self.logging.info("received %s", str(data))
    return data

  def _send_and_receive(self, command_id:int, payload:bytes, expected_size:int):
    self._wt_chip_command(command_id, payload)
    time.sleep(0.1)
    return self._wt_chip_response(expected_size)

  def play_by_index(self, index: int):
    return self._send_and_receive(_play_by_root_index_command_id, index.to_bytes(2, "big"), 1)

  def play_by_name(self, name: int):
    return self._send_and_receive(_play_by_root_name_command_id, name.decode("utf-8"), 1)

  def _process_folder_name(self, folder_name:str):
    length = len(folder_name)
    if length > 5:
      self.logging.error("folder name is longer than allowed 5 chars")
      return None
    if length < 5:
      folder_name += " " * (5 - length)
    return folder_name.encode("utf-8")

  def play_by_folder_index(self, folder_name:str, index: int):
    """
    for folder name are expected 5 characters maximally
    """
    data = self._process_folder_name(folder_name.upper())
    if not data:
      return None

    data += index.to_bytes(2, "big")
    return self._send_and_receive(_play_by_folder_index_command_id, data, 1)

  def play_by_folder_name(self, folder_name: str, track_name: str):
    """
    for folder name are expected 5 characters maximally for file name 8 maximally
    """
    data = self._process_folder_name(folder_name.upper())
    if not data:
      return None

    data += track_name.encode("utf-8")
    return self._send_and_receive(_play_by_folder_name_command_id, data, 1)

  def play_pause(self):
    return self._send_and_receive(_play_pause_command_id, None, 1)

  def stop(self):
    return self._send_and_receive(_stop_command_id, None, 1)

  def play_next(self):
    return self._send_and_receive(_play_next_command_id, None, 1)

  def play_previous(self):
    return self._send_and_receive(_play_previous_command_id, None, 1)

  def combination_play(self, indices:tuple):
    if not self._send_and_receive(_combination_play_command_id, "0x01".to_bytes(1, "big"), 1):
      return False

    for index in indices:
      if not self._send_and_receive(_combination_play_command_id, index.to_bytes(2, "big"), 1):
        return False

    if not self._send_and_receive(_combination_play_command_id, "0xff".to_bytes(1, "big"), 1):
      return False

  def inter_cut_play(self, index:int):
    """
    index defines order of track that starts to play immediately . when finish the original playing track will continue
    """
    return self._send_and_receive(_inter_cut_play_command_id, index.to_bytes(2, "big"), 1)

  def get_track_number(self):
    return self._send_and_receive(_get_track_index_command_id, None, 3)

  def get_volume(self):
    data = self._send_and_receive(_get_volume_command_id, None, 2)
    return data[1] if data else 0

  def set_volume(self, volume):
    return self._send_and_receive(_volume_command_id, volume.to_bytes(1, "big"), 1)

  def get_max_volume(self):
    return _max_volume

  def get_min_volume(self):
    return _min_volume

  def set_play_mode(self, mode:PlayMode):
    self._play_mode = mode
    return self._send_and_receive(_mode_command_id, mode.to_bytes(1, "big"), 1)

  def get_play_mode(self):
    return self._play_mode

  def toggle_play_mode(self):
    if self._play_mode == PlayMode.random_playing:
      self.set_play_mode(PlayMode.single_play)
    else:
      self.set_play_mode(self._play_mode + 1)

  def set_eq_mode(self, mode:EqMode):
    self._eq_mode = mode
    return self._send_and_receive(_eq_mode_command_id, mode.to_bytes(1, "big"), 1)

  def get_eq_mode(self):
    return self._eq_mode

  def toggle_eq_mode(self):
    if self._eq_mode == EqMode.base:
      self.set_eq_mode(EqMode.normal)
    else:
      self.set_eq_mode(self._eq_mode + 1)

  def get_status(self) -> Status:
    data = self._send_and_receive(_get_status_command_id, None, 2)
    if data and data[0] == _get_status_command_id:
      return data[1]
    return None

  def get_track_count(self) -> int:
    data = self._send_and_receive(_get_track_count_command_id, None, 3)
    if data and data[0] == _get_track_count_command_id:
      return (data[1] << 8) + data[2]
    return None

  def get_folder_track_count(self, folder_name:str) -> int:
    in_data = self._process_folder_name(folder_name.upper())
    if not in_data:
      return None

    out_data = self._send_and_receive(_get_folder_track_count_command_id, in_data, 3)
    if out_data and out_data[0] == _get_folder_track_count_command_id:
      return (out_data[1] << 8) + out_data[2]
    return None

  def get_track_name(self) -> str:
    data = self._send_and_receive(_get_track_name_command_id, None, 9)
    if data and data[0] == _get_track_name_command_id:
      return data[1:].decode("utf-8").strip()
    return ""
