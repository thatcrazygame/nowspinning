from typing import Any, Callable, Type, TypeVar
import inspect

from paho.mqtt.client import Client, MQTTMessage
from ha_mqtt_discoverable import Settings, DeviceInfo, Discoverable, EntityInfo
from ha_mqtt_discoverable.sensors import (
    BinarySensorInfo, BinarySensor,
    SensorInfo, Sensor, 
    ButtonInfo, Button
)

from customdiscoverable import SharedSensorInfo, SharedSensor

class MQTTDevice(object):
    def __init__(self, mqtt_settings:Settings, device_info:DeviceInfo,
                 manual_availability=True) -> None:
        self.mqtt_settings = mqtt_settings
        self.device_info = device_info
        self.manual_availability = manual_availability
        self.entities: dict[Discoverable] = {}
        self._shared_sensor_topic = None
        
    @property
    def shared_sensor_topic(self):
        return self._shared_sensor_topic
    
    @shared_sensor_topic.setter
    def shared_sensor_topic(self, value):
        self._shared_sensor_topic = value
        sensors = [s for s in self.entities.values() 
                   if type(s) is SharedSensor]
        for sensor in sensors:
            sensor.state_topic = self._shared_sensor_topic
        
    T = TypeVar("T")
    
    def _add_entity(self, EntityType:Type[Discoverable],
                    manual_availability=None,
                    callback: Callable[[Client, T, MQTTMessage], Any] =
                        lambda c, t, m: None,
                    user_data=None, **entity_info):
        if "device" not in entity_info:
            entity_info["device"] = self.device_info
        
        if manual_availability is None:
            manual_availability = self.manual_availability
            
        entity_signature = inspect.signature(EntityType)

        # TODO find a better way to get this type
        info_type = f"{EntityType.__name__}Info"
        InfoType = globals()[info_type]
        info = InfoType(**entity_info)
        settings = Settings(mqtt=self.mqtt_settings,
                            entity=info,
                            manual_availability=manual_availability)
        
             
        kwargs = {"settings": settings}
        if "command_callback" in entity_signature.parameters:
            kwargs["command_callback"] = callback
        if "user_data" in entity_signature.parameters:
            kwargs["user_data"] = user_data
        
        entity = EntityType(**kwargs)
        self.entities[info.name] = entity
        return entity

    
    def add_binary_sensor(self, manual_availability=None,
                          **entity_info) -> BinarySensor:
        return self._add_entity(BinarySensor,
                                manual_availability,
                                **entity_info)
 
        
    def add_sensor(self, manual_availability=None, **entity_info) -> Sensor:
        return self._add_entity(Sensor,
                                manual_availability,
                                **entity_info)


    def add_shared_sensor(self, manual_availability=None,
                          **entity_info) -> SharedSensor:
        sensor = self._add_entity(SharedSensor,
                                  manual_availability,
                                  **entity_info)
        sensor.state_topic = self.shared_sensor_topic
        return sensor
    
    def add_button(self, callback, user_data=None, manual_availability=None,
                   **entity_info) -> Button:
        return self._add_entity(Button,
                                manual_availability,
                                callback,
                                user_data,
                                **entity_info)