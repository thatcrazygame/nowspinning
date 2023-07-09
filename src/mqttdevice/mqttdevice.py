import inspect
import logging
import ssl
from typing import Any, Callable, Dict, List, Type, TypeVar, Optional

from ha_mqtt_discoverable import Settings, DeviceInfo
import paho.mqtt.client as mqtt

from .custom import (
    Discoverable,
    EntityInfo,
    Subscriber,
    BinarySensorInfo,
    BinarySensor,
    ButtonInfo,
    Button,
    SelectInfo,
    Select,
    SensorInfo,
    Sensor,
    SwitchInfo,
    Switch,
)


logger = logging.getLogger(__name__)


class MQTTDevice(object):
    T = TypeVar("T")

    def __init__(
        self,
        mqtt_settings: Settings.MQTT,
        device_info: DeviceInfo,
        manual_availability=True,
        on_connect: Optional[Callable] = None,
        user_data: T = None,
    ) -> None:
        self.mqtt_settings = mqtt_settings
        self.device_info = device_info
        self.manual_availability = manual_availability
        self.entities: Dict[str, Discoverable] = {}
        self.shared_topic = (
            f"{self.mqtt_settings.state_prefix}/shared/{self.device_info.name}/state"
        )
        self.mqtt_client: mqtt.Client = None
        self._on_connect_callbacks: List[
            Callable[[mqtt.Client, Any, mqtt.MQTTMessage], Any]
        ] = []
        self.user_data = {"data": user_data, "entities": self.entities}

        self._on_connect_callbacks.append(self._subscribe_to_commands)

        self._setup_client(on_connect)

    def _add_entity(
        self,
        EntityType: Type[Discoverable],
        InfoType: Type[EntityInfo],
        manual_availability=None,
        callback: Optional[Callable] = None,
        use_shared_topic=False,
        **entity_info,
    ):
        if "device" not in entity_info:
            entity_info["device"] = self.device_info

        if manual_availability is None:
            manual_availability = self.manual_availability

        entity_signature = inspect.signature(EntityType)

        info = InfoType(**entity_info)
        settings = Settings(
            mqtt=self.mqtt_settings,
            entity=info,
            manual_availability=manual_availability,
        )

        kwargs = {"settings": settings}
        if "command_callback" in entity_signature.parameters:
            kwargs["command_callback"] = callback
        kwargs["mqtt_client"] = self.mqtt_client

        entity = EntityType(**kwargs)
        if use_shared_topic:
            entity.state_topic = self.shared_topic
            entity.availability_topic = self.shared_topic

        self.entities[info.name] = entity
        return entity

    def _setup_client(self, on_connect: Optional[Callable] = None) -> None:
        """Create an MQTT client and setup some basic properties on it"""
        mqtt_settings = self.mqtt_settings
        logger.debug(
            f"Creating mqtt client({mqtt_settings.client_name}) for {mqtt_settings.host}"
        )
        self.mqtt_client = mqtt.Client(mqtt_settings.client_name)
        if mqtt_settings.tls_key:
            logger.info(f"Connecting to {mqtt_settings.host} with SSL")
            logger.debug(f"ca_certs={mqtt_settings.tls_ca_cert}")
            logger.debug(f"certfile={mqtt_settings.tls_certfile}")
            logger.debug(f"keyfile={mqtt_settings.tls_key}")
            self.mqtt_client.tls_set(
                ca_certs=mqtt_settings.tls_ca_cert,
                certfile=mqtt_settings.tls_certfile,
                keyfile=mqtt_settings.tls_key,
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLS,
            )
        else:
            logger.debug(f"Connecting to {mqtt_settings.host} without SSL")
            if mqtt_settings.username:
                self.mqtt_client.username_pw_set(
                    mqtt_settings.username, password=mqtt_settings.password
                )

        if not on_connect:
            on_connect = self._on_client_connect
        logger.debug("Registering custom callback function")
        self.mqtt_client.on_connect = on_connect

        self.mqtt_client.user_data_set(self.user_data)

    def _on_client_connect(self, client: mqtt.Client, *args):
        for callback in self._on_connect_callbacks:
            callback(client, *args)

    def _subscribe_to_commands(self, client: mqtt.Client, *args):
        subscribers = [
            entity
            for entity in self.entities.values()
            if isinstance(entity, Subscriber)
        ]
        for sub in subscribers:
            result, _ = client.subscribe(sub._command_topic, qos=1)
            if result is not mqtt.MQTT_ERR_SUCCESS:
                raise RuntimeError("Error subscribing to MQTT command topic")

    def add_connect_callback(
        self, callback: Callable[[mqtt.Client, Any, mqtt.MQTTMessage], Any]
    ):
        self._on_connect_callbacks.append(callback)

    def connect_client(self) -> None:
        """Connect the client to the MQTT broker, start its onw internal loop in a separate thread"""
        result = self.mqtt_client.connect(self.mqtt_settings.host)
        # Check if we have established a connection
        if result != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError("Error while connecting to MQTT broker")

        # Start the internal network loop of the MQTT library to handle incoming messages in a separate thread
        self.mqtt_client.loop_start()
        self.write_all_configs()

    @property
    def shared_topic_entities(self) -> list[Discoverable]:
        return [s for s in self.entities.values() if s.state_topic == self.shared_topic]

    def set_shared_state(self, state: str | int | float):
        if not self.shared_topic_entities:
            return
        # doesn't matter which, just use the first
        first = self.shared_topic_entities[0]
        first._state_helper(state)

    def write_all_configs(self) -> None:
        entitiy: Discoverable
        for entitiy in self.entities.values():
            entitiy.write_config()

    def set_all_availability(self, availability: bool) -> None:
        entitiy: Discoverable
        for entitiy in self.entities.values():
            entitiy.set_availability(availability)

    def add_binary_sensor(
        self,
        manual_availability=None,
        use_shared_topic=False,
        **entity_info,
    ) -> BinarySensor:
        return self._add_entity(
            BinarySensor,
            BinarySensorInfo,
            manual_availability,
            use_shared_topic,
            **entity_info,
        )

    def add_sensor(
        self,
        manual_availability=None,
        use_shared_topic=False,
        **entity_info,
    ) -> Sensor:
        return self._add_entity(
            Sensor,
            SensorInfo,
            manual_availability,
            use_shared_topic=use_shared_topic,
            **entity_info,
        )

    def add_button(
        self,
        callback,
        manual_availability=None,
        **entity_info,
    ) -> Button:
        return self._add_entity(
            Button,
            ButtonInfo,
            manual_availability,
            callback,
            **entity_info,
        )

    def add_select(
        self,
        callback,
        manual_availability=None,
        use_shared_topic=False,
        **entity_info,
    ) -> Select:
        return self._add_entity(
            Select,
            SelectInfo,
            manual_availability,
            callback,
            use_shared_topic,
            **entity_info,
        )

    def add_switch(
        self,
        callback,
        manual_availability=None,
        use_shared_topic=False,
        **entity_info,
    ) -> Switch:
        return self._add_entity(
            Switch,
            SwitchInfo,
            manual_availability,
            callback,
            use_shared_topic,
            **entity_info,
        )

    def add_subscriber_only(
        self,
        callback,
        sub_topic,
        start_topic,
        start_msg="start",
        manual_availability=None,
        **entity_info,
    ) -> Subscriber:
        entity_info["component"] = "subscriber"
        sub = self._add_entity(
            Subscriber,
            EntityInfo,
            manual_availability,
            callback,
            **entity_info,
        )

        def subscribe_only_callback(client: mqtt.Client, *args):
            client.message_callback_add(sub_topic, callback)
            client.subscribe(sub_topic)
            client.publish(start_topic, start_msg)

        self.add_connect_callback(subscribe_only_callback)

        return sub
