#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

#pylint: disable=no-name-in-module ;implemented in micropython
from micropython import const
#pylint: disable=import-error ;implemented in micropython
import bluetooth
import sys
import struct

from basal import ble_ids as ble_ids
from basal.logging import Logging, LoggerBase
from basal.planner import Planner
from basal.power_mgmt import PowerMgmt, PowerPlan
from basal.active_variable import ActiveVariable
from remote_control.remote_key import RemoteKey

_ADV_TYPE_FLAGS = const(0x01)
_ADV_TYPE_NAME = const(0x09)
_ADV_TYPE_UUID16_COMPLETE = const(0x3)
_ADV_TYPE_APPEARANCE = const(0x19)

_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)

_IRQ_GATTS_INDICATE_DONE = const(20)
_IRQ_MTU_EXCHANGED = const(21)
_IRQ_SET_SECRET = const(30)

_FLAG_READ = const(0x0002)
_FLAG_WRITE_NO_RESPONSE = const(0x0004)
_FLAG_WRITE = const(0x0008)
_FLAG_NOTIFY = const(0x0010)
_FLAG_INDICATE = const(0x0020)

_BMS_MTU = const(256)

_SHELL_COMMAND_CHAR = (
    bluetooth.UUID("48754770-0000-1000-8000-00805F9B34FB"),
    _FLAG_READ | _FLAG_NOTIFY | _FLAG_INDICATE | _FLAG_WRITE | _FLAG_WRITE_NO_RESPONSE,
)

_LOG_CHAR = (
    bluetooth.UUID("48754771-0000-1000-8000-00805F9B34FB"),
    _FLAG_NOTIFY | _FLAG_INDICATE
)

_KEYBOARD_CHAR = (
    bluetooth.UUID("48754772-0000-1000-8000-00805F9B34FB"),
    _FLAG_WRITE
)

_HUGO_SERVICE = (
    bluetooth.UUID("4875476F-0000-1000-8000-00805F9B34FB"),
    (_SHELL_COMMAND_CHAR, _LOG_CHAR, _KEYBOARD_CHAR),
)

#FIXME
_ADV_APPEARANCE_GENERIC_THERMOMETER = const(768)

class BleLogger(LoggerBase):
  message_id = 0 #messages are counted because it seems that notify send one message twice
  def __init__(self):
    super().__init__()

  @classmethod
  def _log_to_ble(cls, message):
    Ble.notify_log(message)

  @classmethod
  def log(cls, level, message):
    Planner.plan(cls._log_to_ble, cls.message_id.to_bytes(1, "big") +  bytes([level]) + message)
    cls.message_id += 1;

class Ble():
  _ble = None
  _shell = None
  _remote_value = None
  _keyboard = None
  _command_handle = None
  _log_handle = None
  _keyboard_handle = None
  _initial_time_up = None
  _running_time_up = None
  _time_down = None
  _time_to_power_save = None
  value_remote: ActiveVariable = ActiveVariable(RemoteKey.get_default())

  @classmethod
  def init(cls) -> None:
    PowerMgmt.register_management_change_callback(cls._set_power_save_timeouts)
    cls._set_power_save_timeouts(PowerMgmt.get_plan()) # to be set defaults
    Planner.plan(cls._check_time_to_power_save, True)

    Logging.add_logger(BleLogger)
    cls._start_ble() #to be allocated big blocks in the beginning it should prevent memory fragmentation
    cls.just_initialized = True

  @classmethod
  def _set_power_save_timeouts(cls, power_plan:PowerPlan):
    cls._initial_time_up = power_plan.ble_plan.initial_time_up
    cls._running_time_up = power_plan.ble_plan.running_time_up
    cls._time_down = power_plan.ble_plan.time_down
    if cls._time_to_power_save != 0: #if ble connection is not established already
      cls._time_to_power_save = cls._initial_time_up

  @classmethod
  def _check_time_to_power_save(cls, wake_up):
    #micropython.mem_info(False)
    go_to_power_save = False
    try: #to do not be _check_time_to_power_save interupted due to a BLE issue
      if wake_up:
        PowerMgmt.block_power_save()
        if not cls._time_to_power_save: #can be reset from constructor
          cls._time_to_power_save = cls._running_time_up
        if cls.just_initialized:
          cls.just_initialized = False
        else:
          cls._start_ble()
        #cls._advertise() #just for sure it is turned on

        print("BLE power-save blocked")
      else:
        if cls._time_to_power_save: #if time was not reset externally (e.g. ble connection)
          cls._time_to_power_save -= 1
          if cls._time_to_power_save == 0: #if time has been reset by decreasing
            go_to_power_save = True
            # ble is disabled automatically when power save is activated and is enabled again when the program runs again
            # but it is not reliable (advertisement si not started) - lets do it manually
            #cls.disconnect()
            cls._stop_ble()
            PowerMgmt.unblock_power_save()
            print("BLE power-save allowed")

    except Exception as error:
      print("BLE error")
      #pylint: disable=no-member ;implemented in micropython
      sys.print_exception(error)
      #micropython.mem_info(0)

    delay = cls._time_down if go_to_power_save else 1
    Planner.postpone(delay, cls._check_time_to_power_save, go_to_power_save)

  @classmethod
  def _start_ble(cls):
    cls._ble = None
    cls._ble = bluetooth.BLE()
    cls._ble.active(True)
    #cls._ble.config(rxbuf=_BMS_MTU)
    cls._ble.irq(cls._irq)

    #cls._ble.config(mtu=_BMS_MTU)
    ((cls._command_handle, cls._log_handle, cls._keyboard_handle), ) = cls._ble.gatts_register_services((_HUGO_SERVICE,))
    cls._connections = set()
    cls._payload = cls.advertising_payload(
        name="HuGo", services=[_HUGO_SERVICE], appearance=_ADV_APPEARANCE_GENERIC_THERMOMETER
    )

    cls._advertise()

  @classmethod
  def _stop_ble(cls):
    cls.disconnect()
    cls._ble.active(False)

  @classmethod
  def get_shell(cls): #saving RAM shell and remote_values are ussually not loaded together
    if not cls._shell:
      from basal.shell import Shell
      cls._shell = Shell
    return cls._shell

  @classmethod
  def get_remote_value(cls):
    if not cls._remote_value:
      from basal.remote_value import RemoteValue
      cls._remote_value = RemoteValue
    return cls._remote_value

  @classmethod
  def process_remote_key(cls, scan_code, key_name):
    if not cls._keyboard:
      from remote_control.virtual_keyboard import VirtualKeyboard
      cls._keyboard = VirtualKeyboard()

    cls.value_remote.set(RemoteKey(key_name, scan_code, cls._keyboard.get_address()))

  @classmethod
  def process_command(cls, conn_handle, value_handle, command, data):
    if command < ble_ids.cmd_shell_last:
      command_solver = cls.get_shell()
    else:
      command_solver = cls.get_remote_value()

    ret_data = command_solver.command_request(command, data)
    if ret_data is not None:
      cls._ble.gatts_notify(conn_handle, value_handle, ret_data)


  @classmethod
  def _irq(cls, event, data):
    # Track connections so we can send notifications.
    if event == _IRQ_CENTRAL_CONNECT:
      conn_handle, _, _ = data
      #NOTE: use when mtu is necessary to change
      connected = False
      for _ in range(3): #sometimes attempts to exchange mtu fails
        try:
          cls._ble.gattc_exchange_mtu(conn_handle)
          connected = True
          cls._time_to_power_save = 0 # disable power save while a connection is active
          break
        except Exception:
          print("Error: gattc_exchange_mtu failed")
      if connected:
        cls._connections.add(conn_handle)
        print("BLE new connection: " + str(conn_handle))
      else:
        cls._ble.gap_disconnect(conn_handle)

    elif event == _IRQ_CENTRAL_DISCONNECT:
      print("disconnect")
      conn_handle, _, _ = data
      cls._connections.remove(conn_handle)
      if not cls._connections:
        cls._time_to_power_save = cls._initial_time_up # enable power save with initial time out - to be possible to reconnect
      print("BLE disconnected " + str(conn_handle))
      # Start advertising again to allow a new connection.
      cls._advertise()
    elif event == _IRQ_GATTS_INDICATE_DONE:
      conn_handle, value_handle, _status = data

    elif event == _IRQ_GATTS_WRITE:
      conn_handle, value_handle = data
      value = cls._ble.gatts_read(value_handle)
      if value_handle == cls._command_handle and value and len(value) > 0:
        command = value[0]
        data = value[1:]

        Planner.plan(cls.process_command, conn_handle, value_handle, command, data)

      if value_handle == cls._keyboard_handle:
        scan_code = int.from_bytes(value[0:2], "big", True)
        key_name = value[2:].decode("utf-8")
        print("scan_code: {}, key_name: {}".format(str(scan_code), str(key_name)))
        Planner.plan(cls.process_remote_key, scan_code, key_name)

    elif event == _IRQ_MTU_EXCHANGED:
      _conn_handle, mtu = data
      print("_IRQ_MTU_EXCHANGED mtu:", mtu)
    elif event == _IRQ_SET_SECRET:
      sec_type, key, value = data
      print("_IRQ_SET_SECRET sec_type:", sec_type, " key:", key, "value", value)
    else:
      print("unhandled event: " + str(event))

  @classmethod
  def is_connected(cls):
    return len(cls._connections) > 0;

  @classmethod
  def advertising_payload(limited_disc=False, br_edr=False, name=None, services=None, appearance=0):
    payload = bytearray()

    def _append(adv_type, value):
      nonlocal payload
      payload += struct.pack("BB", len(value) + 1, adv_type) + value

    _append(
        _ADV_TYPE_FLAGS,
        struct.pack("B", (0x01 if limited_disc else 0x02) + (0x18 if br_edr else 0x04)),
    )

    if name:
      _append(_ADV_TYPE_NAME, name)

    if services:
      _append(_ADV_TYPE_UUID16_COMPLETE, b"HuGo")

    # See org.bluetooth.characteristic.gap.appearance.xml
    if appearance:
      _append(_ADV_TYPE_APPEARANCE, struct.pack("<h", appearance))

    return payload

  @classmethod
  def _advertise(cls, interval_us=100000):
    cls._ble.gap_advertise(interval_us, adv_data=cls._payload)

  @classmethod
  def disconnect(cls):
    for connection in cls._connections:
      cls._ble.gap_disconnect(connection)

  @classmethod
  def notify_log(cls, message):
    try:
      for connection in cls._connections:
        cls._ble.gatts_notify(connection, cls._log_handle, message)
    except Exception as error:
      print("notify_log error: ", error)
