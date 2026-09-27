"""HuGo-specific Zigbee sensor definitions built on the generic native module.

During development this module is imported as ``basal.zigbee``. The
export_devel.py script exports it to the firmware tree as ``basal.zigbee``.
"""

import zigbee

ELECTRICAL_ENDPOINT = 1
WEATHER_ENDPOINT = 2

ELECTRICAL_MEASUREMENT = zigbee.ELECTRICAL_MEASUREMENT
TEMPERATURE_MEASUREMENT = zigbee.TEMPERATURE_MEASUREMENT
RELATIVE_HUMIDITY_MEASUREMENT = zigbee.RELATIVE_HUMIDITY_MEASUREMENT
PRESSURE_MEASUREMENT = zigbee.PRESSURE_MEASUREMENT
WIND_SPEED_MEASUREMENT = zigbee.WIND_SPEED_MEASUREMENT
CO2_MEASUREMENT = zigbee.CO2_MEASUREMENT
ENVIRONMENT_MEASUREMENT = 0xFC00

MEASURED_VALUE = 0x0000
DC_VOLTAGE = 0x0100
DC_CURRENT = 0x0103
WIND_DIRECTION = 0x0000
RAIN_AMOUNT = 0x0001

_endpoints = {}
_clusters = {}

zigbee.configure(manufacturer="HuGo", model="esp32h2", min_join_lqi=0)


class Sensor:
    def __init__(self, attribute, endpoint_id, cluster_id, attribute_id,
                 unit, resolution, minimum, maximum, scale, floating=False):
        self._attribute = attribute
        self.endpoint_id = endpoint_id
        self.cluster_id = cluster_id
        self.attribute_id = attribute_id
        self.role = "server"
        self.unit = unit
        self.resolution = resolution
        self._minimum = minimum
        self._maximum = maximum
        self._scale = scale
        self._floating = floating

    def send(self, value):
        if not self._minimum <= value <= self._maximum:
            raise ValueError("value outside sensor range")
        encoded = value * self._scale
        self._attribute.send(encoded if self._floating else round(encoded))


def _endpoint(endpoint_id):
    endpoint = _endpoints.get(endpoint_id)
    if endpoint is None:
        device_id = (zigbee.CONSUMPTION_AWARENESS
                     if endpoint_id == ELECTRICAL_ENDPOINT else zigbee.SIMPLE_SENSOR)
        endpoint = zigbee.add_endpoint(endpoint_id, device_id=device_id)
        _endpoints[endpoint_id] = endpoint
    return endpoint


def _cluster(endpoint_id, cluster_id):
    key = (endpoint_id, cluster_id)
    cluster = _clusters.get(key)
    if cluster is None:
        cluster = _endpoint(endpoint_id).add_cluster(cluster_id)
        _clusters[key] = cluster
        if cluster_id == ELECTRICAL_MEASUREMENT:
            cluster.add_attribute(0x0000, zigbee.MAP32, 0x00000040,
                                  access=zigbee.READ)
    return cluster


def _attribute(endpoint_id, cluster_id, attribute_id, data_type, initial,
               access=zigbee.READ | zigbee.REPORTING):
    return _cluster(endpoint_id, cluster_id).add_attribute(
        attribute_id, data_type, initial, access=access)


def add_sensor(cluster_id, attribute_id=MEASURED_VALUE, *, endpoint_id=None):
    if cluster_id == ELECTRICAL_MEASUREMENT:
        endpoint_id = ELECTRICAL_ENDPOINT if endpoint_id is None else endpoint_id
        cluster = _cluster(endpoint_id, cluster_id)
        if attribute_id == DC_VOLTAGE:
            value = cluster.add_attribute(attribute_id, zigbee.INT16, -32768)
            cluster.add_attribute(0x0200, zigbee.UINT16, 1, access=zigbee.READ)
            cluster.add_attribute(0x0201, zigbee.UINT16, 100, access=zigbee.READ)
            return Sensor(value, endpoint_id, cluster_id, attribute_id,
                          "V", 0.01, 3.0, 5.0, 100.0)
        if attribute_id == DC_CURRENT:
            value = cluster.add_attribute(attribute_id, zigbee.INT16, -32768)
            cluster.add_attribute(0x0202, zigbee.UINT16, 1, access=zigbee.READ)
            cluster.add_attribute(0x0203, zigbee.UINT16, 10000, access=zigbee.READ)
            return Sensor(value, endpoint_id, cluster_id, attribute_id,
                          "mA", 0.1, 0.1, 1000.0, 10.0)
        raise ValueError("unsupported electrical attribute")

    endpoint_id = WEATHER_ENDPOINT if endpoint_id is None else endpoint_id
    if cluster_id == TEMPERATURE_MEASUREMENT:
        value = _attribute(endpoint_id, cluster_id, attribute_id, zigbee.INT16, -32768)
        _attribute(endpoint_id, cluster_id, 1, zigbee.INT16, -27315, zigbee.READ)
        _attribute(endpoint_id, cluster_id, 2, zigbee.INT16, 32767, zigbee.READ)
        return Sensor(value, endpoint_id, cluster_id, attribute_id,
                      "deg C", 0.01, -273.15, 327.67, 100.0)
    if cluster_id == RELATIVE_HUMIDITY_MEASUREMENT:
        value = _attribute(endpoint_id, cluster_id, attribute_id, zigbee.UINT16, 0xFFFF)
        _attribute(endpoint_id, cluster_id, 1, zigbee.UINT16, 0, zigbee.READ)
        _attribute(endpoint_id, cluster_id, 2, zigbee.UINT16, 10000, zigbee.READ)
        return Sensor(value, endpoint_id, cluster_id, attribute_id,
                      "%", 0.01, 0.0, 100.0, 100.0)
    if cluster_id == PRESSURE_MEASUREMENT:
        value = _attribute(endpoint_id, cluster_id, attribute_id, zigbee.INT16, -32768)
        _attribute(endpoint_id, cluster_id, 1, zigbee.INT16, 0, zigbee.READ)
        _attribute(endpoint_id, cluster_id, 2, zigbee.INT16, 32767, zigbee.READ)
        return Sensor(value, endpoint_id, cluster_id, attribute_id,
                      "hPa", 1.0, 0.0, 32767.0, 1.0)
    if cluster_id == WIND_SPEED_MEASUREMENT:
        value = _attribute(endpoint_id, cluster_id, attribute_id, zigbee.UINT16, 0xFFFF)
        _attribute(endpoint_id, cluster_id, 1, zigbee.UINT16, 0, zigbee.READ)
        _attribute(endpoint_id, cluster_id, 2, zigbee.UINT16, 0xFFFE, zigbee.READ)
        return Sensor(value, endpoint_id, cluster_id, attribute_id,
                      "m/s", 0.01, 0.0, 655.34, 100.0)
    if cluster_id == CO2_MEASUREMENT:
        value = _attribute(endpoint_id, cluster_id, attribute_id, zigbee.FLOAT32, 0.0)
        _attribute(endpoint_id, cluster_id, 1, zigbee.FLOAT32, 0.0, zigbee.READ)
        _attribute(endpoint_id, cluster_id, 2, zigbee.FLOAT32, 1.0, zigbee.READ)
        return Sensor(value, endpoint_id, cluster_id, attribute_id,
                      "ppm", 0.01, 0.0, 1000000.0, 0.000001, True)
    if cluster_id == ENVIRONMENT_MEASUREMENT:
        if attribute_id == WIND_DIRECTION:
            value = _attribute(endpoint_id, cluster_id, attribute_id, zigbee.UINT16, 0xFFFF)
            return Sensor(value, endpoint_id, cluster_id, attribute_id,
                          "deg", 0.01, 0.0, 359.99, 100.0)
        if attribute_id == RAIN_AMOUNT:
            value = _attribute(endpoint_id, cluster_id, attribute_id, zigbee.UINT32, 0xFFFFFFFF)
            return Sensor(value, endpoint_id, cluster_id, attribute_id,
                          "mm", 0.01, 0.0, 42949672.95, 100.0)
    raise ValueError("unsupported cluster or attribute")


start = zigbee.start
joined = zigbee.joined
status = zigbee.status
join = zigbee.join
factory_reset = zigbee.factory_reset
