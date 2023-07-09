import json
import logging
import ssl
from importlib import metadata
from typing import Any, Callable, Generic, Optional, TypeVar

import paho.mqtt.client as mqtt
from paho.mqtt.client import MQTTMessageInfo
from pydantic import BaseModel, dataclasses, root_validator
from pydantic.generics import GenericModel

import ha_mqtt_discoverable as hamd

logger = logging.getLogger(__name__)


class EntityInfo(hamd.EntityInfo):
    """custom"""


EntityType = TypeVar("EntityType", bound=EntityInfo)


class Discoverable(hamd.Discoverable[EntityType]):
    def __init__(
        self,
        settings: hamd.Settings[EntityType],
        mqtt_client: Optional[mqtt.Client] = None,
        on_connect: Optional[Callable] = None,
    ) -> None:
        """
        Creates a basic discoverable object.

        Args:
            settings: Settings for the entity we want to create in Home Assistant.
            See the `Settings` class for the available options.
            on_connect: Optional callback function invoked when the MQTT client successfully connects to the broker.
            If defined, you need to call `_connect_client() to establish the connection manually.`
        """
        # Import here to avoid circular dependency on imports
        # TODO how to better handle this?
        from ha_mqtt_discoverable.utils import clean_string

        self._settings = settings
        self._entity = settings.entity

        # Build the topic string: start from the type of component
        # e.g. `binary_sensor`
        self._entity_topic = f"{self._entity.component}"
        # If present, append the device name, e.g. `binary_sensor/mydevice`
        self._entity_topic += (
            f"/{clean_string(self._entity.device.name)}" if self._entity.device else ""
        )
        # Append the sensor name, e.g. `binary_sensor/mydevice/mysensor`
        self._entity_topic += f"/{clean_string(self._entity.name)}"

        # Full topic where we publish the configuration message to be picked up by HA
        # Prepend the `discovery_prefix`, default: `homeassistant`
        # e.g. homeassistant/binary_sensor/mydevice/mysensor
        self.config_topic = (
            f"{self._settings.mqtt.discovery_prefix}/{self._entity_topic}/config"
        )
        # Full topic where we publish our own state messages
        # Prepend the `state_prefix`, default: `hmd`
        # e.g. hmd/binary_sensor/mydevice/mysensor
        self.state_topic = (
            f"{self._settings.mqtt.state_prefix}/{self._entity_topic}/state"
        )

        # Full topic where we publish our own attributes as JSON messages
        # Prepend the `state_prefix`, default: `hmd`
        # e.g. hmd/binary_sensor/mydevice/mysensor
        self.attributes_topic = (
            f"{self._settings.mqtt.state_prefix}/{self._entity_topic}/attributes"
        )

        logger.info(f"config_topic: {self.config_topic}")
        logger.info(f"state_topic: {self.state_topic}")
        if self._settings.manual_availability:
            # Define the availability topic, using `hmd` topic prefix
            self.availability_topic = (
                f"{self._settings.mqtt.state_prefix}/{self._entity_topic}/availability"
            )
            logger.debug(f"availability_topic: {self.availability_topic}")

        if mqtt_client:
            self.mqtt_client = mqtt_client
        else:
            # Create the MQTT client, registering the user `on_connect` callback
            self._setup_client(on_connect)
            # If there is a callback function defined, the user must manually connect to the MQTT client
            if not on_connect:
                self._connect_client()


class Subscriber(Discoverable[EntityType]):
    """
    Specialized subclass that listens to commands coming from an MQTT topic
    """

    T = TypeVar("T")  # Used in the callback function

    def __init__(
        self,
        settings: hamd.Settings[EntityType],
        command_callback: Callable[[mqtt.Client, T, mqtt.MQTTMessage], Any],
        mqtt_client: Optional[mqtt.Client] = None,
    ) -> None:
        """
        Entity that listens to commands from an MQTT topic.

        Args:
            settings: Settings for the entity we want to create in Home Assistant.
            See the `Settings` class for the available options.
            command_callback: Callback function invoked when there is a command
            coming from the MQTT command topic
        """

        # Invoke the parent init
        super().__init__(settings, mqtt_client)
        # Define the command topic to receive commands from HA
        self._command_topic = f"{self._entity_topic}/command"

        self.mqtt_client.message_callback_add(self._command_topic, command_callback)

    def generate_config(self) -> dict[str, Any]:
        """Override base config to add the command topic of this switch"""
        config = super().generate_config()
        # Add the MQTT command topic to the existing config object
        topics = {
            "command_topic": self._command_topic,
        }
        return config | topics


class BinarySensorInfo(EntityInfo):
    """Binary sensor specific information"""

    component: str = "binary_sensor"
    off_delay: Optional[int] = None
    """For sensors that only send on state updates (like PIRs),
    this variable sets a delay in seconds after which the sensor's state will be updated back to off."""
    payload_off: str = "off"
    """Payload to send for the ON state"""
    payload_on: str = "on"
    """Payload to send for the OFF state"""

    value_template: str = None
    availability_template: str = None


class SensorInfo(EntityInfo):
    """Sensor specific information"""

    component: str = "sensor"
    unit_of_measurement: Optional[str] = None
    """Defines the units of measurement of the sensor, if any."""

    value_template: str = None
    availability_template: str = None


class SwitchInfo(EntityInfo):
    """Switch specific information"""

    component: str = "switch"
    optimistic: Optional[bool] = None
    """Flag that defines if switch works in optimistic mode.
    Default: true if no state_topic defined, else false."""
    payload_off: str = "OFF"
    """The payload that represents off state. If specified, will be used for both comparing
    to the value in the state_topic (see value_template and state_off for details)
    and sending as off command to the command_topic"""
    payload_on: str = "ON"
    """The payload that represents on state. If specified, will be used for both comparing
     to the value in the state_topic (see value_template and state_on for details)
     and sending as on command to the command_topic."""
    retain: Optional[bool] = None
    """If the published message should have the retain flag on or not"""
    state_topic: Optional[str] = None
    """The MQTT topic subscribed to receive state updates."""

    value_template: str = None
    availability_template: str = None


class ButtonInfo(EntityInfo):
    """Button specific information"""

    component: str = "button"

    payload_press: str = "PRESS"
    """The payload to send to trigger the button."""
    retain: Optional[bool] = None
    """If the published message should have the retain flag on or not"""

    availability_template: str = None


class TextInfo(EntityInfo):
    """Information about the `text` entity"""

    component: str = "text"

    max: int = 255
    """The maximum size of a text being set or received (maximum is 255)."""
    min: int = 0
    """The minimum size of a text being set or received."""
    mode: Optional[str] = "text"
    """The mode off the text entity. Must be either text or password."""
    pattern: Optional[str] = None
    """A valid regular expression the text being set or received must match with."""

    retain: Optional[bool] = None
    """If the published message should have the retain flag on or not"""

    value_template: str = None
    availability_template: str = None


class DeviceTriggerInfo(EntityInfo):
    """Information about the device trigger"""

    component: str = "device_automation"
    automation_type: str = "trigger"
    """The type of automation, must be ‘trigger’."""

    payload: Optional[str] = None
    """Optional payload to match the payload being sent over the topic."""
    type: str
    """The type of the trigger"""
    subtype: str
    """The subtype of the trigger"""
    device: hamd.DeviceInfo
    """Information about the device this sensor belongs to (required)"""

    value_template: str = None
    availability_template: str = None


class SelectInfo(EntityInfo):
    """Select specific Information"""

    component: str = "select"
    options: list[str] = []
    value_template: str
    availability_template: str = None


class BinarySensor(Discoverable[BinarySensorInfo]):
    def off(self):
        """
        Set binary sensor to off
        """
        self._update_state(state=False)

    def on(self):
        """
        Set binary sensor to on
        """
        self._update_state(state=True)

    def _update_state(self, state: bool) -> None:
        """
        Update MQTT sensor state

        Args:
            state(bool): What state to set the sensor to
        """
        if state:
            state_message = self._entity.payload_on
        else:
            state_message = self._entity.payload_off
        logger.info(
            f"Setting {self._entity.name} to {state_message} using {self.state_topic}"
        )
        self._state_helper(state=state_message)


class Sensor(Discoverable[SensorInfo]):
    def set_state(self, state: str | int | float) -> None:
        """
        Update the sensor state

        Args:
            state(str): What state to set the sensor to
        """
        logger.info(f"Setting {self._entity.name} to {state} using {self.state_topic}")
        self._state_helper(str(state))


# Inherit the on and off methods from the BinarySensor class, changing only the documentation string
class Switch(Subscriber[SwitchInfo], BinarySensor):
    """Implements an MQTT switch:
    https://www.home-assistant.io/integrations/switch.mqtt
    """

    def off(self):
        """
        Set switch to off
        """
        super().off()

    def on(self):
        """
        Set switch to on
        """
        super().on()


class Button(Subscriber[ButtonInfo]):
    """Implements an MQTT button:
    https://www.home-assistant.io/integrations/button.mqtt
    """


class DeviceTrigger(Discoverable[DeviceTriggerInfo]):
    """Implements an MWTT Device Trigger
    https://www.home-assistant.io/integrations/device_trigger.mqtt/
    """

    def generate_config(self) -> dict[str, Any]:
        """Publish a custom configuration:
        since this entity does not provide a `state_topic`, HA expects a `topic` key in the config
        """
        config = super().generate_config()
        # Publish our `state_topic` as `topic`
        topics = {
            "topic": self.state_topic,
        }
        return config | topics

    def trigger(self, payload: Optional[str] = None):
        """
        Generate a device trigger event

        Args:
            payload: custom payload to send in the trigger topic

        """
        return self._state_helper(payload, self.state_topic, retain=False)


class Text(Subscriber[TextInfo]):
    """Implements an MQTT text:
    https://www.home-assistant.io/integrations/text.mqtt/
    """

    def set_text(self, text: str) -> None:
        """
        Update the text displayed by this sensor. Check that it is of acceptable length.

        Args:
            text(str): Value of the text configured for this entity
        """
        if not self._entity.min <= len(text) <= self._entity.max:
            raise RuntimeError(
                f"Text is not within configured length boundaries [{self._entity.min}, {self._entity.max}]"
            )

        logger.info(f"Setting {self._entity.name} to {text} using {self.state_topic}")
        self._state_helper(str(text))


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
