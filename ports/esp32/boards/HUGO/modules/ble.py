import bluetooth
import struct
from micropython import const

_ADV_TYPE_FLAGS = const(0x01)
_ADV_TYPE_NAME = const(0x09)
_ADV_TYPE_UUID16_COMPLETE = const(0x3)
_ADV_TYPE_APPEARANCE = const(0x19)

_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)

_IRQ_GATTS_INDICATE_DONE = const(20)
_IRQ_MTU_EXCHANGED = const(21)

_FLAG_READ = const(0x0002)
_FLAG_WRITE_NO_RESPONSE = const(0x0004)
_FLAG_WRITE = const(0x0008)
_FLAG_NOTIFY = const(0x0010)
_FLAG_INDICATE = const(0x0020)

_BMS_MTU = const(256)

_SHELL_GET_PROPERTY_CHAR = (
    bluetooth.UUID("48754770-0000-1000-8000-00805F9B34FB"),
    _FLAG_READ | _FLAG_NOTIFY | _FLAG_INDICATE | _FLAG_WRITE | _FLAG_WRITE_NO_RESPONSE,
)

_SHELL_SET_PROPERTY_CHAR = (
    bluetooth.UUID("48754771-0000-1000-8000-00805F9B34FB"),
    _FLAG_READ | _FLAG_NOTIFY | _FLAG_INDICATE | _FLAG_WRITE | _FLAG_WRITE_NO_RESPONSE,
)

_SHELL_COMMAND_CHAR = (
    bluetooth.UUID("48754772-0000-1000-8000-00805F9B34FB"),
    _FLAG_READ | _FLAG_NOTIFY | _FLAG_INDICATE | _FLAG_WRITE | _FLAG_WRITE_NO_RESPONSE,
)

_LOG_CHAR = (
    bluetooth.UUID("48754773-0000-1000-8000-00805F9B34FB"),
    _FLAG_NOTIFY | _FLAG_INDICATE
)

_HUGO_SERVICE = (
    bluetooth.UUID("4875476F-0000-1000-8000-00805F9B34FB"),
    (_SHELL_COMMAND_CHAR, _LOG_CHAR,),
)

#FIXME
_ADV_APPEARANCE_GENERIC_THERMOMETER = const(768)

class Ble():
  def __init__(self, shell_command_callback) -> None:
    self._ble = bluetooth.BLE()
    self._shell_command_callback = shell_command_callback
    self._shell_command_handle = None
    self._log_handle = None
    self._start_ble()

  def _start_ble(self):
    self._ble.active(True)
    self._ble.config(rxbuf=_BMS_MTU)
    self._ble.irq(self._irq)

    #self._ble.config(mtu=_BMS_MTU)
    ((self._shell_command_handle,self._log_handle, ), ) = self._ble.gatts_register_services((_HUGO_SERVICE,))
    self._connections = set()
    self._payload = self.advertising_payload(
        name="HuGo", services=[_HUGO_SERVICE], appearance=_ADV_APPEARANCE_GENERIC_THERMOMETER
    )

    self._advertise()
    #print("ble advertise")

  def _irq(self, event, data):
    # Track connections so we can send notifications.
    if event == _IRQ_CENTRAL_CONNECT:
      conn_handle, _, _ = data
      self._connections.add(conn_handle)
      #NOTE: use when mtu is necessary to change
      self._ble.gattc_exchange_mtu(conn_handle)
      print("BLE new connection: " + str(conn_handle))
    elif event == _IRQ_CENTRAL_DISCONNECT:
      conn_handle, _, _ = data
      self._connections.remove(conn_handle)
      print("BLE disconnected " + str(conn_handle))
      # Start advertising again to allow a new connection.
      self._advertise()
    elif event == _IRQ_GATTS_INDICATE_DONE:
      conn_handle, value_handle, status = data

    elif event == _IRQ_GATTS_WRITE:
      conn_handle, value_handle = data
      #print ("write " + str((conn_handle, value_handle)))
      value = self._ble.gatts_read(value_handle)
      #print(("value",value))
      if value_handle == self._shell_command_handle:
        ret_data = self._shell_command_callback(value)
        if ret_data is not None:
          self._ble.gatts_notify(conn_handle, value_handle, ret_data)
        #print("notification sent:" + str(ret_data))
    elif event == _IRQ_MTU_EXCHANGED:
      pass
      #conn_handle, mtu = data
      #print("mtu set to: ", str(mtu))
    else:
      print("unhandled event: " + str(event))

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

  def _advertise(self, interval_us=100000):
    self._ble.gap_advertise(interval_us, adv_data=self._payload)

  def disconnect(self):
    for connection in self._connections:
      self._ble.gap_disconnect(connection)

  def notify_log(self, message):
    for connection in self._connections:
      self._ble.gatts_notify(connection, self._log_handle, message)