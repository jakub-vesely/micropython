#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

import machine

class BlePowerPlan:

  def __init__(self, initial_time_up, running_time_up, time_down) -> None:
    """
    @param param initial_time_up: defines how long will be ble preserve from power saving (this time allow faster and more reliable programming)
    @param running_runing_time_up: defines time when ble waits for a new connection if the connection is not established BLE is turned off to be power saving enabled
      4 sec is reliable (but can happen that connect is not managed when scaning starts in the middle of an "up" window),
      3 sec is still quite reliable,
      2 sec usually does not manage scanning and connect in one window but fillowing connection is reliable,
      1 sec have a lot of unsuccessful attempts for connection but it is still "usable" when is necessary to decrease power consumption (just the programming can be longer)
    @param time_down : determines time for which is BLE disabled

    if initial_time_up and running_runing_time_up are equal to 0 power saving is disabled
    """
    self.initial_time_up = initial_time_up
    self.running_time_up = running_time_up
    self.time_down = time_down

class PowerPlan:
  freq_max = 240000000
  freq_medium = 160000000
  freq_min = 80000000

  def __init__(self, power_save_enabled, frequency, ble_plan:BlePowerPlan) -> None:
    self.power_save_enabled = power_save_enabled
    self.frequency = frequency
    self.ble_plan = ble_plan

  @staticmethod
  def get_max_performance_plan():
    return PowerPlan(False, PowerPlan.freq_max, BlePowerPlan(0, 0, 0))

  @staticmethod
  def get_balanced_plan():
    return PowerPlan(True, PowerPlan.freq_medium, BlePowerPlan(90, 3, 12))

  @staticmethod
  def get_power_saving_plan():
    return PowerPlan(True, PowerPlan.freq_min, BlePowerPlan(30, 1, 60))

class PowerMgmt:
  _power_save_block_count = 0 #can be increased/decreased by more modules. power save is blocked when the block count > 0
  _used_plan = PowerPlan.get_max_performance_plan() #FIXME: will be started with maximal frequency if is not called set_plan explicitly
  _change_callbacks = list()
  #_start_light_sleep_callbacks = list()
  #_stop_light_sleep_callbacks = list()
  #_logging = Logging("PwrMgmt")

  @classmethod
  def block_power_save(cls):
    cls._power_save_block_count += 1

  @classmethod
  def unblock_power_save(cls):
    cls._power_save_block_count -= 1

  @classmethod
  def is_power_save_enabled(cls):
    return cls._power_save_block_count == 0

  @classmethod
  def set_plan(cls, plan:PowerPlan):
    cls._used_plan = plan
    for callback in cls._change_callbacks:
      callback(cls._used_plan)
    machine.freq(cls._used_plan.frequency)

  @classmethod
  def get_plan(cls) -> PowerPlan:
    return cls._used_plan

  @classmethod
  def light_sleep(cls, duration):
    #for start_callback in cls._start_light_sleep_callbacks:
    #  start_callback()

    machine.freq(PowerPlan.freq_min)
    machine.lightsleep(duration)
    machine.freq(cls._used_plan.frequency)

    #for stop_callback in cls._stop_light_sleep_callbacks:
    #  stop_callback()


  @classmethod
  def register_management_change_callback(cls, method):
    """
    @param methodL is expected callback method with PowerPlan as a parameter
    """
    cls._change_callbacks.append(method)

  # @classmethod
  # def register_light_sleep_start_callback(cls, method):
  #   """
  #   @param methodL is expected callback method with no parameter
  #   """
  #   cls._start_light_sleep_callbacks.append(method)

  # @classmethod
  # def register_light_sleep_stop_callback(cls, method):
  #   """
  #   @param methodL is expected callback method with no parameter
  #   """
  #   cls._stop_light_sleep_callbacks.append(method)

