from ha_mqtt_discoverable import Discoverable, EntityInfo
from ha_mqtt_discoverable.sensors import SensorInfo, Sensor

class SharedSensorInfo(SensorInfo):
    value_template: str
    

class SharedSensor(Sensor, Discoverable[SharedSensorInfo]):
    """Sensor with value_template"""