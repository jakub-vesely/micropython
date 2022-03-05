#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

from blocks.motor_driver_block import MotorDriverBlock
from basal.logging import Logging
from blocks.power_block import PowerBlock
from blocks.block_base import PowerSaveLevel

class State:
  def __init__(self, left, right, pwm) -> None:
    self.left = left
    self.right = right
    self.pwm = pwm

class Direction:
  backward = 0
  forward = 1

class Speed:
  stop = 0
  slow = 1
  normal = 2
  fast = 3

class Manoeuver:
  rotate_left = 0
  sharply_left = 1
  slightly_left = 2
  straight = 3
  slightly_right = 4
  sharply_right = 5
  rotate_right = 6

class Chassis:
  state = {}
  def __init__(self, address_driver_front=0x20, address_driver_rear=0x21, addr_power=None, power_measurement_period=1):
    self.speed = Speed.stop
    self.manoeuver = Manoeuver.straight
    self.direction = Direction.forward
    self.logging = Logging("chassis")
    self.power = PowerBlock(addr_power, power_measurement_period)
    self.front_driver = MotorDriverBlock(address_driver_front)
    self.rear_driver = MotorDriverBlock(address_driver_rear)

  def _set_driver_values(self, driver:MotorDriverBlock, left_speed, right_speed, pwm):
    positive_speed = left_speed if left_speed > 0 else left_speed * -1
    if left_speed > 0 and self.direction == Direction.forward:
      driver.turn_clockwise(MotorDriverBlock.motor1_id)
    else:
      driver.turn_opposite(MotorDriverBlock.motor1_id)
    driver.set_speed(MotorDriverBlock.motor1_id, positive_speed)

    positive_speed = right_speed if right_speed > 0 else right_speed * -1
    if right_speed > 0 and self.direction == Direction.forward:
      driver.turn_opposite(MotorDriverBlock.motor2_id)
    else:
      driver.turn_clockwise(MotorDriverBlock.motor2_id)
    driver.set_speed(MotorDriverBlock.motor2_id, positive_speed)
    driver.set_pwm_period(pwm)

  def _set_values(self, l_speed, r_speed, pwm):
    #self.logging.info("l_speed: {0}, r_speed: {1}, pwm: {2}".format(l_speed, r_speed, pwm))
    self._set_driver_values(self.front_driver, l_speed, r_speed, pwm)
    self._set_driver_values(self.rear_driver, l_speed, r_speed, pwm)

  def _adjust_movement(self):
    #self.logging.info("direction: {0}, speed: {1}, manoeuver: {2}".format(self.direction, self.speed, self.manoeuver))
    if self.speed == Speed.fast:
      if self.manoeuver == Manoeuver.rotate_left:
        self._set_values(l_speed=90, r_speed=-90, pwm=50)
      elif self.manoeuver == Manoeuver.sharply_left:
        self._set_values(l_speed=100, r_speed=0, pwm=50)
      elif self.manoeuver == Manoeuver.slightly_left:
        self._set_values(l_speed=100, r_speed=20, pwm=80)
      elif self.manoeuver == Manoeuver.straight:
        self._set_values(l_speed=90, r_speed=90, pwm=50)
      elif self.manoeuver == Manoeuver.slightly_right:
        self._set_values(l_speed=20, r_speed=100, pwm=80)
      elif self.manoeuver == Manoeuver.sharply_right:
        self._set_values(l_speed=0, r_speed=100, pwm=50)
      elif self.manoeuver == Manoeuver.rotate_right:
        self._set_values(l_speed=-90, r_speed=90, pwm=50)

    elif self.speed == Speed.normal:
      if self.manoeuver == Manoeuver.rotate_left:
        self._set_values(l_speed=70, r_speed=-70, pwm=50)
      elif self.manoeuver == Manoeuver.sharply_left:
        self._set_values(l_speed=70, r_speed=0, pwm=80)
      elif self.manoeuver == Manoeuver.slightly_left:
        self._set_values(l_speed=70, r_speed=15, pwm=80)
      elif self.manoeuver == Manoeuver.straight:
        self._set_values(l_speed=60, r_speed=60, pwm=50)
      elif self.manoeuver == Manoeuver.slightly_right:
        self._set_values(l_speed=15, r_speed=70, pwm=80)
      elif self.manoeuver == Manoeuver.sharply_right:
        self._set_values(l_speed=0, r_speed=70, pwm=80)
      elif self.manoeuver == Manoeuver.rotate_right:
        self._set_values(l_speed=-70, r_speed=70, pwm=80)

    elif self.speed == Speed.slow:
      if self.manoeuver == Manoeuver.rotate_left:
        self._set_values(l_speed=40, r_speed=-40, pwm=80)
      elif self.manoeuver == Manoeuver.sharply_left:
        self._set_values(l_speed=40, r_speed=0, pwm=80)
      elif self.manoeuver == Manoeuver.slightly_left:
        self._set_values(l_speed=50, r_speed=15, pwm=80)
      elif self.manoeuver == Manoeuver.straight:
        self._set_values(l_speed=30, r_speed=30, pwm=80)
      elif self.manoeuver == Manoeuver.slightly_right:
        self._set_values(l_speed=15, r_speed=50, pwm=80)
      elif self.manoeuver == Manoeuver.sharply_right:
        self._set_values(l_speed=0, r_speed=40, pwm=80)
      elif self.manoeuver == Manoeuver.rotate_right:
        self._set_values(l_speed=-40, r_speed=40, pwm=80)

    elif self.speed == Speed.stop:
      self._set_values(0, 0, 80)

  def set_direction(self, direction:Direction):
    if direction > Direction.forward:
      self.direction = Direction.forward
    elif direction < Direction.backward:
      self.direction = Direction.backward
    else:
      self.direction = direction
    self._adjust_movement()

  def set_speed(self, speed:Speed):
    if speed < Speed.stop:
      self.speed = Speed.stop
    elif speed > Speed.fast:
      self.speed = Speed.fast
    else:
      self.speed = speed
    self._adjust_movement()

  def set_manoeuver(self, manoeuver:Manoeuver):
    if manoeuver < Manoeuver.rotate_left:
      self.manoeuver = Manoeuver.rotate_left
    elif manoeuver > Manoeuver.rotate_right:
      self.manoeuver = Manoeuver.rotate_right
    else:
      self.manoeuver = manoeuver
    self._adjust_movement()

  def counter_sensors_on(self):
    self.front_driver.sensor_power_on()
    self.rear_driver.sensor_power_on()

  def counter_sensors_off(self):
    self.front_driver.sensor_power_off()
    self.rear_driver.sensor_power_off()

  def get_counters(self):
    """
    returns: counts of wheel sensor changes in order [ front left, front right, rear left, rear right
    """
    counter_fl = self.front_driver.get_sensor_counter(MotorDriverBlock.motor1_id)
    counter_fr = self.front_driver.get_sensor_counter(MotorDriverBlock.motor2_id)
    counter_rl = self.rear_driver.get_sensor_counter(MotorDriverBlock.motor1_id)
    counter_rr = self.rear_driver.get_sensor_counter(MotorDriverBlock.motor2_id)
    return (counter_fl, counter_fr, counter_rl, counter_rr)

  def get_lr_counters(self):
    """
    returns: left and right counts of wheel sensor changes
    """
    counter_fl, counter_fr, counter_rl, counter_rr = self.get_counters()
    return (int((counter_fl + counter_rl) / 2), int((counter_fr + counter_rr) / 2))

  def power_save(self, level:PowerSaveLevel) -> None:
    self.power.power_save()
    self.front_driver.power_save()
    self.rear_driver.power_save()