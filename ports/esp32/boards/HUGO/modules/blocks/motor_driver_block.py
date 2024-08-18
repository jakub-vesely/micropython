#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

from blocks.block_types import BlockTypes
from blocks.block_base import BlockBase
from basal.active_variable import ActiveVariable

class Speed:
  speed_0 = 0
  speed_20 = 20
  speed_40 = 40
  speed_60 = 60
  speed_80 = 80
  speed_100 = 100

class MotorDriverBlock(BlockBase):
  turn_clockwise_command = 1
  turn_anticlockwise_command = 2
  stop_command = 3
  power_off_command = 4
  power_on_command = 5
  reset_counter_command = 6
  get_counter_command = 7
  set_speed_command = 8
  set_pwm_period_command = 9

  motor1_id = 1
  motor2_id = 2

  def __init__(self, address=None, get_counter_period=1):
    super().__init__(BlockTypes.motor_driver, address)
    self.motor1_sensor_counter = ActiveVariable(0, get_counter_period, self._get_sensor_counter_m1)
    self.motor2_sensor_counter = ActiveVariable(0, get_counter_period, self._get_sensor_counter_m2)

  def _send_simple_command(self, command_id, motor_id=None, data=None):
    if motor_id:
      full_data = motor_id.to_bytes(1, "big", False)
      if data:
        full_data += data
    else:
      full_data = data
    self._tiny_write(command_id, full_data)

  def turn_clockwise(self, motor_id):
    self._send_simple_command(self.turn_clockwise_command, motor_id)

  def turn_opposite(self, motor_id):
    self._send_simple_command(self.turn_anticlockwise_command, motor_id)

  def stop(self, motor_id):
    self._send_simple_command(self.stop_command, motor_id)

  def sensor_power_off(self):
    self._send_simple_command(self.power_off_command)

  def sensor_power_on(self):
    self._send_simple_command(self.power_on_command)

  def reset_sensor_counter(self, motor_id):
    self._send_simple_command(self.reset_counter_command, motor_id)

  def _get_sensor_counter_m1(self):
    return self.get_sensor_counter(self.motor1_id)

  def _get_sensor_counter_m2(self):
    return self.get_sensor_counter(self.motor2_id)

  def get_sensor_counter(self, motor_id):
    data = self._tiny_read(self.get_counter_command, motor_id.to_bytes(1, "big", False), 4)
    return int.from_bytes(data, "big", False)

  def set_speed(self, motor_id, speed: int):
    """
    @param speed: expected int from 0 to 10
    """
    if speed < 0:
      speed = 0
    if speed > 100:
      speed = 100
    #self.logging.info("motor_id", motor_id, "speed", speed)
    self._send_simple_command(self.set_speed_command, motor_id, speed.to_bytes(1, "big", False))

  def set_pwm_period(self, period):
    """expected period in the range (1 to 100) where the step is 10ms"""
    if period > 255:
      period = 255
    if period < 1:
      period = 1
    self._send_simple_command(self.set_pwm_period_command, data=period.to_bytes(1, "big", False))
