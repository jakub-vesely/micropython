import logging
from power_block import PowerBlock
from motor_driver_block import MotorDriverBlock
from logging import Logging
class Direction():
  forward = 1
  backward = 2

class Chassis():
  # f - forward
  # b - backward
  # c - clockwise
  # a - anticlockwise (opposite)

  # func          | dir | turn  | l_rot | r_rot | l_speed | r_speed
  #---------------|-----|-------|-------|-------|---------|---------
  # go_left(100)  | f   | -100  | c     | c     | 100     | 100
  # go_left(100)  | b   | -100  | a     | a     | 100     | 100
  #
  # go_left(50)   | f   | -50   | a/c   | c     | 0       | 100
  # go_left(50)   | b   | -50   | a/c   | a     | 0       | 100
  #
  # go_straight() | f   | 0     | a     | c     | 100     | 100
  # go_straight() | b   | 0     | c     | a     | 100     | 100
  #
  # go_right(25)  | f   | 25    | a     | c     | 100     | 50
  # go_right(25)  | b   | 25    | c     | a     | 100     | 50
  #
  # go_right(50)  | f   | 50    | a     | a/c   | 100     | 0
  # go_right(50)  | b   | 50    | c     | a/c   | 100     | 0
  #
  # go_right(75)  | f   | 75    | a     | a     | 100     | 50
  # go_right(75)  | b   | 75    | c     | c     | 100     | 50
  #
  # go_right(100) | f   | 100   | a     | a     | 100     | 100
  # go_right(100) | b   | 100   | c     | c     | 100     | 100

  # turning | -100 | -75 | -50 | -25 | 0   | 25  | 50  | 75  | 100
  #---------|------|-----|-----|-----|-----|-----|-----|-----|-----
  # speed l | 100  | 50  |  0  | 50  | 100 | 100 | 100 | 100 | 100
  # speed r | 100  | 100 | 100 | 100 | 100 | 50  | 0   | 50  | 100

  logging = Logging("chassis")
  left_id = MotorDriverBlock.motor2_id
  right_id = MotorDriverBlock.motor1_id

  def __init__(self, addr_power, addr_front_driver, addr_rear_driver):
    self.power = PowerBlock(addr_power)
    self.front_driver = MotorDriverBlock(addr_front_driver)
    self.front_driver.set_pwm_period(0)
    self.rear_driver = MotorDriverBlock(addr_rear_driver)
    self.rear_driver.set_pwm_period(0)

    self.direction = Direction.forward
    self.turning = 0 #expected numbers -100 left max; 100 right max
    self.speed = 0 #expected 0 - no move; 100 - max speed

  def _set_limits(self):
    if self.speed < 0:
      self.speed = 0
    if self.speed > 100:
      self.speed = 100
    if self.turning < -100:
      self.turning = -100
    if self.turning > 100:
      self.turning = 100

  def _adjust_motion(self):
    self._set_limits()

    if (self.direction == Direction.forward and self.turning >= -50) or (self.direction == Direction.backward and self.turning < -50):
      self.front_driver.turn_opposite(self.left_id)
      self.rear_driver.turn_opposite(self.left_id)
    else:
      self.front_driver.turn_clockwise(self.left_id)
      self.rear_driver.turn_clockwise(self.left_id)

    if (self.direction == Direction.forward and self.turning >= 50) or (self.direction == Direction.backward and self.turning < 50):
      self.front_driver.turn_opposite(self.right_id)
      self.rear_driver.turn_opposite(self.right_id)
    else:
      self.front_driver.turn_clockwise(self.right_id)
      self.rear_driver.turn_clockwise(self.right_id)

    l_factor = 1
    r_factor = 1
    if self.turning < 0 and self.turning >= -50:
      l_factor = (100 + self.turning * 2) * 0.01
    elif self.turning < -50:
      l_factor = ((self.turning + 50) * 2) * -0.01

    if self.turning >= 0 and self.turning < 50:
      r_factor = (50 - self.turning) * 2 * 0.01
    elif self.turning >= 50:
      r_factor = ((self.turning - 50) * 2) * 0.01

    self.logging.info(("l_factor", l_factor))
    self.logging.info(("r_factor", r_factor))

    self.front_driver.set_speed(self.left_id, int(float(self.speed) * l_factor))
    self.front_driver.set_speed(self.right_id, int(float(self.speed) * r_factor))
    self.rear_driver.set_speed(self.left_id, int(float(self.speed) * l_factor))
    self.rear_driver.set_speed(self.right_id, int(float(self.speed) * r_factor))

  def go_forward(self, speed=100):
    """
    @param: factor: ; expected number in range 0 - 100
    """
    self.direction = Direction.forward
    self.speed = speed
    self._adjust_motion()

  def go_backward(self, speed=100):
    """
    @param: factor: ; expected number in range 0 - 100
    """
    self.direction = Direction.backward
    self.speed = speed
    self._adjust_motion()

  def stop(self):
    self.speed = 0
    self.turning = 0
    self._adjust_motion()

  def turn_left(self, factor):
    """
    @param: factor: ; factor of turning 0 (no turing) - 100 (max turning)
    """
    self.turning = -factor
    self._adjust_motion()

  def turn_right(self, factor):
    """
    @param: factor: ; factor of turning 0 (no turing) - 100 (max turning)
    """
    self.turning = factor
    self._adjust_motion()

  def sensors_on(self):
    self.front_driver.sensor_power_on()
    self.rear_driver.sensor_power_on()

  def sensors_off(self):
    self.front_driver.sensor_power_off()
    self.rear_driver.sensor_power_off()
