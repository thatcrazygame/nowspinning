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
        if set(options) == set(self._entity.options):
            return
        self._entity.options = options
        self.write_config()

    def set_selection(self, option: str) -> None:
        if option in self._entity.options:
            self._state_helper(str(option))

    def set_availability(self, availability: bool = None):
        if availability is None:
            has_opts = bool(self._entity.options)
            availability = has_opts

        super().set_availability(availability)
