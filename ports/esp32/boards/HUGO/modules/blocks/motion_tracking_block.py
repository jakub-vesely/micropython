#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

import struct

from blocks.block_types import BlockTypes
from blocks.extended_block_base import BlockWithOneExtension
from blocks.block_base import PowerSaveLevel
from basal.active_variable import ActiveVariable
from basal.active_quantity import ActiveQuantity
from basal.shell import Shell
from quantities.temperature import Temperature
from mpu9250 import MPU9250
from mpu6500 import MPU6500, SF_DEG_S
from ak8963 import AK8963

class MotionTrackingBlock(BlockWithOneExtension):
  _gyro_offset_calibration_file_name = "._gyro_offset_cal"
  _mag_offset_calibration_file_name = "._mag_offset_cal"
  _mag_scale_calibration_file_name = "._mag_scale_cal"

  def __init__(self, address=None, measurement_period: float=1):
    """
    @param address:block address
    @param measurement_period: sampling frequency in sec
    """
    super().__init__(BlockTypes.motion_tracking, address)
    self.acceleration = ActiveVariable(0, measurement_period, self._get_acceleration)
    self.gyro = ActiveVariable(0, measurement_period, self._get_gyro)
    self.magnetic = ActiveVariable(0, measurement_period, self._get_magnetic)
    self.temperature = ActiveQuantity(Temperature(), 0, measurement_period, self._get_temperature)

    self._mag_offset_calibration = self._file_to_cal(self._mag_offset_calibration_file_name)
    self._mag_scale_calibration = self._file_to_cal(self._mag_scale_calibration_file_name)
    self._gyro_offset_calibration = self._file_to_cal(self._gyro_offset_calibration_file_name)
    self.logging.info(("_mag_offset_calibration", self._mag_offset_calibration))
    self.logging.info(("_mag_scale_calibration", self._mag_scale_calibration))
    #doesn't make sense to initialize extension when the block is not inserted
    self._mpu6500 = None
    self._ak8963 = None

    if self.is_available():
      _dummy = MPU9250(self.i2c) # this opens the bybass to access to the AK8963

      if (self._gyro_offset_calibration):
        self.logging.info("gyro calibration will be used")

      self._mpu6500 = MPU6500(
        self.i2c,
        gyro_offset = self._gyro_offset_calibration if self._gyro_offset_calibration else (0, 0, 0),
        gyro_sf=SF_DEG_S
      )

      if (self._mag_offset_calibration and self._mag_scale_calibration):
        self.logging.info("mag calibration will be used")

      self._ak8963 = AK8963(
        self.i2c,
        offset = self._mag_offset_calibration if self._mag_offset_calibration else (0, 0, 0),
        scale = self._mag_scale_calibration if self._mag_scale_calibration else (0, 0, 0),
      )

  def _get_acceleration(self):
    if self._mpu6500 and self.power_save_level == PowerSaveLevel.NoPowerSave:
      return self._mpu6500.acceleration
    return None

  def _get_gyro(self):
    if self._mpu6500 and self.power_save_level == PowerSaveLevel.NoPowerSave:
      return self._mpu6500.gyro
    return None

  def _get_magnetic(self):
    if self._ak8963 and self.power_save_level == PowerSaveLevel.NoPowerSave:
      return self._ak8963.magnetic
    return None

  def _get_temperature(self):
    if self._mpu6500 and self.power_save_level == PowerSaveLevel.NoPowerSave:
      return self._mpu6500.temperature
    return None

  def is_magnetic_calibrated(self):
    return self._mag_offset_calibration is not None

  def is_gyro_calibrated(self):
    return self._gyro_offset_calibration is not None

  def _cal_to_file(self, calibration, file_path):
    cal_bytes = b""
    for item in calibration:
      cal_bytes += struct.pack("f", item)
    self.logging.info("written" + str(calibration) + " to " + file_path)
    Shell.create_file(file_path, cal_bytes)

  def _file_to_cal(self, file_path):
    if not Shell.file_exists(file_path):
      self.logging.warning("file " + file_path  + " not exists")
      return None

    data =  Shell.get_file_content(file_path)
    if not data:
      self.logging.warning("file" + file_path  + " does not contain any data")
      return None

    return struct.unpack('fff', data)

  def calibrate_magnetic(self):
    if not self._ak8963:
      return False

    calibration = self._ak8963.calibrate(count=256, delay=100)
    self.logging.info(("calibration", calibration))
    self._cal_to_file(calibration[0], self._mag_offset_calibration_file_name)
    self._cal_to_file(calibration[1], self._mag_scale_calibration_file_name)
    return True

  def calibrate_gyro(self):
    if not self._mpu6500:
      return False

    calibration = self._mpu6500.calibrate()
    self._cal_to_file(calibration, self._gyro_offset_calibration_file_name)
    return True

  def power_save(self, level:PowerSaveLevel) -> None:
    #TODO:
    pass
