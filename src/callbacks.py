import json
import logging
from typing import TypedDict, Dict

from constants import (
    DAILY,
    FORECAST_TYPE,
    INFO_PAYLOAD_LEN,
    SECONDARY_DEFAULT,
    SECONDARY_TYPE,
)

# from customdiscoverable import Select
from data import Data
from mqttdevice import Discoverable
from paho.mqtt.client import Client, MQTTMessage

logger = logging.getLogger(__name__)


class _UserData(TypedDict):
    data: Data
    entities: Dict[str, Discoverable]


def _process_message(message: MQTTMessage, is_json: bool = False):
    payload = str(message.payload.decode("UTF-8"))

    log = f"MQTT Message: {message.topic} >"
    payload_short = " ".join(payload.split())[:INFO_PAYLOAD_LEN]
    ellipsis = "..." if len(payload) > INFO_PAYLOAD_LEN else ""

    logger.info(f"{log} {payload_short}{ellipsis}")
    logger.debug(f"{log} {payload}")
    if is_json:
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            logger.exception(f"Invalid json payload: {payload}")
            payload = json.loads("{}")

    return payload


def teamtracker(client: Client, user_data: _UserData, message: MQTTMessage):
    if "selected_game" not in message.topic and "all_games" not in message.topic:
        return

    payload = _process_message(message, is_json=True)
    if "selected_game" in message.topic:
        user_data["data"].selected_game = payload
    if "all_games" in message.topic:
        user_data["data"].all_games = payload


def update_view(client: Client, user_data: _UserData, message: MQTTMessage):
    view = _process_message(message)
    user_data["data"].view = view


def music_switch(client: Client, user_data: _UserData, message: MQTTMessage):
    state = _process_message(message)
    user_data["data"].switch_to_music = state == "ON"


def averages(client: Client, user_data: _UserData, message: MQTTMessage):
    payload = _process_message(message, is_json=True)
    if "averages" not in payload:
        return

    user_data["data"].averages = payload["averages"]


def game_of_life_buttons(client: Client, user_data: _UserData, message: MQTTMessage):
    payload = _process_message(message)
    user_data["data"].game_of_life_commands.put_nowait(payload)


def game_of_life_gens_switch(
    client: Client, user_data: _UserData, message: MQTTMessage
):
    state = _process_message(message)
    user_data["data"].game_of_life_show_gens = state == "ON"


def game_of_life_spt(client: Client, user_data: _UserData, message: MQTTMessage):
    seconds = _process_message(message)
    user_data["data"].game_of_life_seconds_per_tick = float(seconds)


def weather(client: Client, user_data: _UserData, message: MQTTMessage):
    payload = _process_message(message, is_json=True)
    if "condition" not in payload:
        return

    user_data["data"].weather_forecast = payload


def update_forecast_type(client: Client, user_data: _UserData, message: MQTTMessage):
    f_type = _process_message(message)
    if f_type not in FORECAST_TYPE:
        f_type = DAILY
    user_data["data"].forecast_type = f_type


def update_secondary_type(client: Client, user_data: _UserData, message: MQTTMessage):
    s_type = _process_message(message)
    if s_type not in SECONDARY_TYPE:
        s_type = SECONDARY_DEFAULT.name
    user_data["data"].secondary_type = s_type


def songrec_reset_button(client: Client, user_data: _UserData, message: MQTTMessage):
    payload = _process_message(message)
    if payload == "RESET":
        user_data["data"].reset_music()


def music_timeout_number(client: Client, user_data: _UserData, message: MQTTMessage):
    seconds = _process_message(message)
    user_data["data"].music_timeout = seconds
