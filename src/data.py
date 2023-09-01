import asyncio
from base64 import b64decode
from io import BytesIO
import json
import logging
from time import perf_counter

from dbus_next.errors import DBusError
from PIL import Image, ImageChops

from constants import View, HOURLY, DAILY
from eqstream import EQStream
from img_funcs import get_dominant_colors, get_min_constrast_colors
from sports import League, Team
from viewdraw import ViewDrawer

SONGREC_TIMEOUT_SECS = 30.0 * 60.0

logger = logging.getLogger(__name__)


class Data(object):
    """Class to share data between async functions"""

    def __init__(self):
        self.is_running = True
        self.view: View = View.OFF
        self.view_drawers: dict[View, ViewDrawer] = {}
        self.switch_to_music: bool = False

        self.reset_music()
        self.eq_stream: EQStream = EQStream()
        self.eq_stream.listen()

        self.temperature = None
        self.humidity = None
        self.co2 = None
        self.voc = None
        self.raw_gas = None
        self.averages: dict[str, list[float]] = {}

        self.sports: dict[str, League] = {}
        self.selected_league_abbr: str = None
        self.selected_team_abbr: str = None

        self.game_of_life_commands = asyncio.Queue()
        self.game_of_life_cells: int = 0
        self.game_of_life_generations: int = 0
        self.game_of_life_show_gens: bool = False

        self.weather_forecast: dict = None
        self.forecast_type: str = DAILY

    def reset_music(self):
        logger.info("Reset music")
        self._artists: list[str] = None
        self.title = "Listening..."
        self.album = None
        self.album_art = Image.open("../img/microphone.jpeg")
        self.album_art_colors = None
        self.music_last_updated = None

    def stop(self, signum, frame):
        logger.info("Stopping...")
        self.eq_stream.stop()
        self.is_running = False

    def _str(self, val, round_digits=None) -> str:
        is_number = type(val) is int or type(val) is float
        if is_number:
            val = f"{round(val, round_digits)}"

        return str(val) if val is not None else ""

    def _on_off(self, b: bool, line: str = "") -> str:
        return f"{'on' if b else 'off'}{line}"

    @property
    def temperature_f(self) -> float:
        if self.temperature is None:
            return None
        else:
            return (self.temperature * 1.8) + 32.0

    @property
    def artists(self) -> str:
        artists_str = ""
        if self._artists is not None:
            artists_str = f"{','.join(self._artists)}"
        return artists_str

    @property
    def selected_league(self) -> League:
        if not self.selected_league_abbr:
            return None

        return self.sports[self.selected_league_abbr]

    @property
    def selected_team(self) -> Team:
        if not self.selected_league:
            return None

        league = self.selected_league
        team: Team = None

        if self.selected_team_abbr:
            team = league.team(self.selected_team_abbr)
        else:
            teams = list(league.teams.values())
            teams.sort(key=Team.by_game_state, reverse=True)
            team = teams[0]
            self.selected_team_abbr = team.abbr

        return team

    def get_payload(self) -> dict:
        payload = {}
        payload["temperature"] = {
            "value": self._str(self.temperature_f, round_digits=1),
            "available": "online",
        }
        payload["humidity"] = {
            "value": self._str(self.humidity, round_digits=1),
            "available": "online",
        }
        payload["co2"] = {"value": self._str(self.co2), "available": "online"}
        payload["voc"] = {"value": self._str(self.voc), "available": "online"}
        payload["artist"] = {"value": self.artists, "available": "online"}
        payload["album"] = {"value": self._str(self.album), "available": "online"}
        payload["title"] = {"value": self._str(self.title), "available": "online"}
        payload["view"] = {"value": self._str(self.view.value), "available": "online"}
        payload["league"] = {
            "value": self._str(self.selected_league_abbr),
            "available": self._on_off(bool(self.sports), "line"),
        }
        team_name = self.selected_team.friendly_name if self.selected_team else ""
        payload["team"] = {
            "value": self._str(team_name),
            "available": self._on_off(bool(self.sports), "line"),
        }
        payload["music_switch"] = {
            "value": self._on_off(self.switch_to_music).upper(),
            "available": "online",
        }
        payload["gol_generations"] = {
            "value": self._str(self.game_of_life_generations),
            "available": "online",
        }
        payload["gol_cells"] = {
            "value": self._str(self.game_of_life_cells),
            "available": "online",
        }
        payload["gol_show_gens"] = {
            "value": self._on_off(self.game_of_life_show_gens).upper(),
            "available": self._on_off(self.view is View.GAME_OF_LIFE, "line"),
        }
        payload["gol_reset"] = {
            "value": None,
            "available": self._on_off(self.view is View.GAME_OF_LIFE, "line"),
        }
        payload["gol_add_noise"] = {
            "value": None,
            "available": self._on_off(self.view is View.GAME_OF_LIFE, "line"),
        }
        payload["forecast_type"] = {
            "value": self._str(self.forecast_type),
            "available": "online",
        }

        return payload

    def get_json(self) -> str:
        return json.dumps(self.get_payload())

    async def refresh_music_data(self, player, width, height):
        metadata = None
        try:
            metadata = await player.get_metadata()
        except DBusError as e:
            self.album_art = Image.open("../img/microphone-off.jpeg")
            self.title = "Service unavailable"
            logger.exception("DBUS Error")
            return

        if not metadata:
            return

        self.music_last_updated = perf_counter()

        if "xesam:artist" in metadata:
            self._artists = metadata["xesam:artist"].value
        if "xesam:title" in metadata:
            self.title = metadata["xesam:title"].value
        if "xesam:album" in metadata:
            self.album = metadata["xesam:album"].value
        if "mpris:artUrl" in metadata:
            art_str = metadata["mpris:artUrl"].value
            art_str = art_str.replace("data:image/jpeg;base64,", "")
            art_base64 = BytesIO(b64decode(art_str))
            art_image = Image.open(art_base64)
            art_image.thumbnail((width, height), Image.Resampling.LANCZOS)

            diff = ImageChops.difference(art_image, self.album_art)
            art_changed = diff.getbbox() is not None

            self.album_art = art_image

            if art_changed or self.album_art_colors is None:
                colors = get_dominant_colors(art_image)
                self.album_art_colors = get_min_constrast_colors(colors)

        logger.info(
            f"Refresh music - artist(s): {self.artists} title: {self.title} album: {self.album}"
        )

        if self.switch_to_music:
            self.view = View.MUSIC

    def views_by_last_drawn(self, exclude: list[View] = [View.MUSIC]):
        views = [
            (drawer.last_drawn, view)
            for view, drawer in self.view_drawers.items()
            if view not in exclude
        ]
        views.sort(key=lambda v: v[0], reverse=True)
        views = [view[1] for view in views]
        return views

    def check_songrec_timeout(self):
        recognized = self.music_last_updated is not None
        if not recognized:
            return

        now = perf_counter()
        timedout = (now - self.music_last_updated) >= SONGREC_TIMEOUT_SECS

        if not timedout:
            return

        if self.view is View.MUSIC and self.switch_to_music:
            sorted_views = self.views_by_last_drawn()
            self.view = sorted_views[0]

        self.reset_music()
