from basal.logging import Logging
import time
import network

class WiFi:
    sta_if = None
    logging = Logging("Plan")

    @classmethod
    def connect(cls, ssid, password):
        cls.sta_if = network.WLAN(network.STA_IF)
        cls.sta_if.active(True)
        cls.sta_if.connect("veselovi", "asdfgh123")

    @classmethod
    def is_connected(cls):
        if not cls.sta_if:
            return False
        return cls.sta_if.isconnected()

    @classmethod
    def get_config(cls):
        if not cls.sta_if:
            return ""
        return cls.sta_if.ifconfig()

    @classmethod
    def get_rssi(cls):
        if not cls.sta_if:
            return ""
        return cls.sta_if.status('rssi');

    @classmethod
    def scan(cls):
        return cls.sta_if.scan()

    @classmethod
    def post(cls, url, data):
        import urequests as requests
        res = requests.get('https://www.google.com')
        cls.logging.info(res.status_code)

