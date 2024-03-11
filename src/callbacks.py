import json
import logging
from typing import TypedDict, Dict

from constants import DAILY, FORECAST_TYPE, GameState, View

# from customdiscoverable import Select
from data import Data
from mqttdevice import Discoverable
from paho.mqtt.client import Client, MQTTMessage
from sports import League, Team

logger = logging.getLogger(__name__)
INFO_PAYLOAD_LEN = 50


class __UserData(TypedDict):
    data: Data
    entities: Dict[str, Discoverable]


def __process_message(message: MQTTMessage, is_json: bool = False):
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


def teamtracker(client: Client, user_data: __UserData, message: MQTTMessage):
    payload = __process_message(message, is_json=True)
    if "teams" not in payload:
        return

    json_teams = payload["teams"]

    for team in json_teams:
        league_abbr = team["league"]
        team_abbr = team["team_abbr"]

        if not league_abbr or not team_abbr:
            continue

        if league_abbr not in user_data["data"].sports:
            user_data["data"].sports[league_abbr] = League(league_abbr)

        state: GameState
        try:
            state = GameState[team["state"].upper()]
        except KeyError:
            logger.warning(f"Invalid GameState: {team['state'].upper()}")
            continue

        new_attr: dict = team["attributes"]

        for attr in new_attr:
            if type(new_attr[attr]) is list:
                new_attr[attr] = tuple(new_attr[attr])

        team = user_data["data"].sports[league_abbr].team(team_abbr)
        prev_attr = team.attributes

        diff = dict(set(new_attr.items()) - set(prev_attr.items()))

        user_data["data"].sports[league_abbr].team(
            team_abbr, attributes=new_attr, changes=diff, game_state=state
        )

    # remove unused leagues
    leagues = list(set([team["league"] for team in json_teams]))
    user_data["data"].sports = {
        abbr: league
        for abbr, league in user_data["data"].sports.items()
        if abbr in leagues
    }

    selected_league_abbr = user_data["data"].selected_league_abbr
    if selected_league_abbr not in user_data["data"].sports:
        selected_league_abbr = list(user_data["data"].sports.keys())[0]
        user_data["data"].selected_league_abbr = selected_league_abbr
    selected_league = user_data["data"].selected_league

    # mark game state of unused teams None which removes it from the select options
    for l_abbr, league in user_data["data"].sports.items():
        for t_abbr, team in league.teams.items():
            json_team = [
                t
                for t in json_teams
                if t["team_abbr"] == t_abbr and t["league"] == l_abbr
            ]
            if json_team:
                continue
            team.game_state = None

    active_teams = [
        t.abbr
        for t in selected_league.teams.values()
        if t.game_state is not GameState.UNAVAILABLE
    ]
    if user_data["data"].selected_team_abbr not in active_teams:
        teams = list(selected_league.teams.values())
        teams.sort(key=Team.by_game_state, reverse=True)
        first_team = teams[0]
        user_data["data"].selected_team_abbr = first_team.abbr


def update_team(client: Client, user_data: __UserData, message: MQTTMessage):
    selected_name = __process_message(message)
    if not (selected_name and user_data["data"].selected_league_abbr):
        return

    league = user_data["data"].selected_league
    for team in league.teams.values():
        team_name = team.friendly_name
        if team_name and team_name == selected_name:
            user_data["data"].selected_team_abbr = team.abbr
            break


def update_league(client: Client, user_data: __UserData, message: MQTTMessage):
    league_abbr = __process_message(message)

    diff_league = user_data["data"].selected_league_abbr != league_abbr
    if league_abbr in user_data["data"].sports and diff_league:
        user_data["data"].selected_league_abbr = league_abbr
        league: League = user_data["data"].selected_league
        if not league.teams:
            return

        teams = list(league.teams.values())
        teams.sort(key=Team.by_game_state, reverse=True)
        first_team = teams[0]
        user_data["data"].selected_team_abbr = first_team.abbr
        team_names = league.friendly_team_names
        user_data["entities"]["Team"].update_options(team_names)
        user_data["entities"]["Team"].set_selection(None)  # Maybe helps reset?


def update_view(client: Client, user_data: __UserData, message: MQTTMessage):
    view = __process_message(message)
    user_data["data"].view = View(view)


def music_switch(client: Client, user_data: __UserData, message: MQTTMessage):
    state = __process_message(message)
    user_data["data"].switch_to_music = state == "ON"


def averages(client: Client, user_data: __UserData, message: MQTTMessage):
    payload = __process_message(message, is_json=True)
    if "averages" not in payload:
        return

    user_data["data"].averages = payload["averages"]


def game_of_life_buttons(client: Client, user_data: __UserData, message: MQTTMessage):
    payload = __process_message(message)
    user_data["data"].game_of_life_commands.put_nowait(payload)


def game_of_life_gens_switch(
    client: Client, user_data: __UserData, message: MQTTMessage
):
    state = __process_message(message)
    user_data["data"].game_of_life_show_gens = state == "ON"


def game_of_life_spt(client: Client, user_data: __UserData, message: MQTTMessage):
    seconds = __process_message(message)
    user_data["data"].game_of_life_seconds_per_tick = float(seconds)


def weather(client: Client, user_data: __UserData, message: MQTTMessage):
    payload = __process_message(message, is_json=True)
    if "condition" not in payload:
        return

    user_data["data"].weather_forecast = payload


def update_forecast_type(client: Client, user_data: __UserData, message: MQTTMessage):
    f_type = __process_message(message)
    if f_type not in FORECAST_TYPE:
        f_type = DAILY
    user_data["data"].forecast_type = f_type


def songrec_reset_button(client: Client, user_data: __UserData, message: MQTTMessage):
    payload = __process_message(message)
    if payload == "RESET":
        user_data["data"].reset_music()


def music_timeout_number(client: Client, user_data: __UserData, message: MQTTMessage):
    seconds = __process_message(message)
    user_data["data"].music_timeout = seconds
