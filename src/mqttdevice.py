from typing import Any, Callable, Type, TypeVar
import inspect

from paho.mqtt.client import Client, MQTTMessage
from ha_mqtt_discoverable import (
    Settings,
    DeviceInfo,
    Discoverable,
    EntityInfo,
    Subscriber
)

from ha_mqtt_discoverable.sensors import (
    BinarySensorInfo, BinarySensor,
    ButtonInfo, Button,
    SensorInfo, Sensor,
    SwitchInfo, Switch 
)

from customdiscoverable import (
    SelectInfo, Select,
    SharedSensorInfo, SharedSensor
)

class MQTTDevice(object): 
    T = TypeVar("T")
    
    def __init__(self, mqtt_settings:Settings, device_info:DeviceInfo,
                 manual_availability=True) -> None:
        self.mqtt_settings = mqtt_settings
        self.device_info = device_info
        self.manual_availability = manual_availability
        self.entities: dict[Discoverable] = {}
        self._shared_sensor_topic = None

            
    @property     
    def shared_sensor_entities(self) -> list[SharedSensor]:
        return [s for s in self.entities.values() if type(s) is SharedSensor]
    
    
    @property
    def shared_sensor_topic(self):
        return self._shared_sensor_topic
    
    
    @shared_sensor_topic.setter
    def shared_sensor_topic(self, value):
        self._shared_sensor_topic = value
        sensors = self.shared_sensor_entities
        for sensor in sensors:
            sensor.state_topic = self._shared_sensor_topic
            
            
    def set_shared_state(self, state: str | int | float):
        if not self.shared_sensor_entities:
            return    
        # doesn't matter which, just use the first
        first = self.shared_sensor_entities[0]
        first.set_state(state)
        
        
    def write_all_configs(self):
        for entitiy in self.entities.values():
            entitiy.write_config()

    
    def _add_entity(self, EntityType:Type[Discoverable],
                    InfoType:Type[EntityInfo], manual_availability=None,
                    always_available=True,
                    callback: Callable[[Client, T, MQTTMessage], Any] =
                        lambda c, t, m: None,
                    user_data=None, **entity_info):
        if "device" not in entity_info:
            entity_info["device"] = self.device_info
        
        if manual_availability is None:
            manual_availability = self.manual_availability
            
        entity_signature = inspect.signature(EntityType)

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
        entity.always_available = always_available
        self.entities[info.name] = entity
        return entity

    
    def add_binary_sensor(self, manual_availability=None, 
                          always_available=True,
                          **entity_info) -> BinarySensor:
        return self._add_entity(BinarySensor,
                                BinarySensorInfo,
                                manual_availability,
                                always_available,
                                **entity_info)
 
        
    def add_sensor(self, manual_availability=None, always_available=True,
                   **entity_info) -> Sensor:
        return self._add_entity(Sensor, SensorInfo, manual_availability,
                                always_available, **entity_info)


    def add_shared_sensor(self, manual_availability=None,
                          always_available=True, 
                          **entity_info) -> SharedSensor:
        sensor = self._add_entity(SharedSensor,
                                  SharedSensorInfo, 
                                  manual_availability,
                                  always_available,
                                  **entity_info)
        sensor.state_topic = self.shared_sensor_topic
        return sensor
    
    
    def add_button(self, callback, user_data=None, manual_availability=None,
                   always_available=True, **entity_info) -> Button:
        return self._add_entity(Button,
                                ButtonInfo,
                                manual_availability,
                                always_available,
                                callback,
                                user_data,
                                **entity_info)
        
    
    def add_select(self, callback, user_data=None, manual_availability=None,
                   always_available=True, **entity_info) -> Select:
        return self._add_entity(Select,
                                SelectInfo,
                                manual_availability,
                                always_available,
                                callback,
                                user_data,
                                **entity_info)
        
    
    def add_switch(self, callback, user_data=None, manual_availability=None,
                   always_available=True, **entity_info) -> Switch:
        return self._add_entity(Switch, 
                                SwitchInfo,
                                manual_availability,
                                always_available,
                                callback,
                                user_data,
                                **entity_info)
        
    
    def add_subscriber_only(self, callback, user_data, sub_topic, start_topic,
                            start_msg = "start", manual_availability=None,
                            always_available=True, 
                            **entity_info) -> Subscriber:
        entity_info["component"] = "subscriber"
        sub = self._add_entity(Subscriber,
                               EntityInfo,
                               manual_availability,
                               always_available,
                               callback,
                               user_data,
                               **entity_info)
        
        sub.mqtt_client.subscribe(sub_topic)
        sub.mqtt_client.publish(start_topic, start_msg)
        
        return sub