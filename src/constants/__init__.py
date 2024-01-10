from enum import Enum, auto
from rgbmatrix.graphics import Color


class AutoValue(Enum):
    def _generate_next_value_(name, start, count, last_values):
        return name.replace("_", " ").title()


class View(AutoValue):
    OFF = auto()
    DASHBOARD = auto()
    MUSIC = auto()
    SCOREBOARD = auto()
    GAME_OF_LIFE = auto()
    WEATHER = auto()


class GameState(Enum):
    # values represent priority, not chronological order
    UNAVAILABLE = -1
    NOT_FOUND = 0
    BYE = 1
    POST = 2
    PRE = 3
    IN = 4


PANEL_WIDTH = 64
PANEL_HEIGHT = 64

HOURLY = "Hourly"
DAILY = "Daily"
FORECAST_TYPE = {HOURLY, DAILY}
