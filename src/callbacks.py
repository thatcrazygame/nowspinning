import json
from typing import TypedDict, Dict

from constants import GameState, View

# from customdiscoverable import Select
from data import Data
from mqttdevice import Discoverable
from paho.mqtt.client import Client, MQTTMessage
from sports import League, Team


class __UserData(TypedDict):
    data: Data
    entities: Dict[str, Discoverable]


def teamtracker(client: Client, user_data: __UserData, message: MQTTMessage):
    payload = json.loads(str(message.payload.decode("UTF-8")))
    if "teams" not in payload:
        return

    for team in payload["teams"]:
        league_abbr = team["league"]
        team_abbr = team["team_abbr"]

        if league_abbr not in user_data["data"].sports:
            user_data["data"].sports[league_abbr] = League(league_abbr)

        state: GameState = GameState[team["state"].upper()]
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


def update_team(client: Client, user_data: __UserData, message: MQTTMessage):
    selected_name = str(message.payload.decode("UTF-8"))
    if not (selected_name and user_data["data"].selected_league_abbr):
        return

    league = user_data["data"].sports[user_data["data"].selected_league_abbr]
    for team in league.teams.values():
        team_name = team.friendly_name
        if team_name and team_name == selected_name:
            user_data["data"].selected_team_abbr = team.abbr
            break


def update_league(client: Client, user_data: __UserData, message: MQTTMessage):
    league_abbr = str(message.payload.decode("UTF-8"))

    diff_league = user_data["data"].selected_league_abbr != league_abbr
    if league_abbr in user_data["data"].sports and diff_league:
        user_data["data"].selected_league_abbr = league_abbr
        league: League = user_data["data"].sports[league_abbr]
        if not league.teams:
            return

        teams = list(league.teams.values())
        teams.sort(key=Team.by_game_state, reverse=True)
        first_team = teams[0]
        user_data["data"].selected_team_abbr = first_team.abbr
        # team_select = mqtt.entities["Team"]
        team_names = league.friendly_team_names
        user_data["entities"]["Team"].update_options(team_names)
        user_data["entities"]["Team"].set_selection(None)  # Maybe helps reset?


def update_view(client: Client, user_data: __UserData, message: MQTTMessage):
    view = str(message.payload.decode("UTF-8"))
    user_data["data"].view = View(view)


def music_switch(client: Client, user_data: __UserData, message: MQTTMessage):
    state = str(message.payload.decode("UTF-8"))
    user_data["data"].switch_to_music = state == "ON"


def averages(client: Client, user_data: __UserData, message: MQTTMessage):
    payload = json.loads(str(message.payload.decode("UTF-8")))
    if "averages" not in payload:
        return

    user_data["data"].averages = payload["averages"]


def game_of_life_buttons(client: Client, user_data: __UserData, message: MQTTMessage):
    payload = str(message.payload.decode("UTF-8"))
    user_data["data"].game_of_life_commands.put_nowait(payload)


def game_of_life_gens_switch(
    client: Client, user_data: __UserData, message: MQTTMessage
):
    state = str(message.payload.decode("UTF-8"))
    user_data["data"].game_of_life_show_gens = state == "ON"
