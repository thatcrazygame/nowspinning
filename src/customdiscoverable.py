from ha_mqtt_discoverable import Discoverable, EntityInfo, Subscriber
from ha_mqtt_discoverable.sensors import SensorInfo, Sensor
from typing import Any, Optional

class SharedSensorInfo(SensorInfo):
    value_template: str
    

class SharedSensor(Sensor, Discoverable[SharedSensorInfo]):
    """Sensor with value_template"""
    

class SelectInfo(EntityInfo):
    """Select specific Information"""
    component: str = "select"
    options: list[str] = []


class Select(Subscriber[SelectInfo]):
    """Implements an MQTT select:
    https://www.home-assistant.io/integrations/select.mqtt
    """
    def update_options(self, options: list[str]) -> None:
        self._entity.options = options
        self.write_config()


    def set_selection(self, option: str) -> None:
        if option in self._entity.options:
            # Not sure if both are needed
            self._state_helper(str(option), topic=self._command_topic)
            self._state_helper(str(option))


    