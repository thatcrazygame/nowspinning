from enum import Enum
import numpy as np
from constants.colors import BLACK, WHITE
from zoneinfo import ZoneInfo


class GameState(Enum):
    # values represent priority, not chronological order
    UNAVAILABLE = -1
    NOT_FOUND = 0
    BYE = 1
    POST = 2
    PRE = 3
    IN = 4


""" Scrolling Text """
DIR_LEFT = -1
DIR_RIGHT = 1
ALIGN_LEFT = "ALIGN_LEFT"
ALIGN_RIGHT = "ALIGN_RIGHT"
ALIGN_CENTER = "ALIGN_CENTER"

""" Device and Default settings """
PANEL_WIDTH = 64
PANEL_HEIGHT = 64
FAN_PIN = 25
METERS_ABOVE_SEA_LEVEL = 274
TEMPERATURE_OFFSET = 6.0
INFO_PAYLOAD_LEN = 50
SONGREC_TIMEOUT_SECS = 30.0 * 60.0

""" VIEW NAMES """
ALLGAMES = "All Games"
DASHBOARD = "Dashboard"
GAMEOFLIFE = "Game of Life"
MUSIC = "Music"
OFF = "Off"
SCOREBOARD = "Scoreboard"
WEATEHR = "Weather"
DEFAULT_VIEW = OFF

""" Image Utils """
RGB = tuple[float, float, float] | tuple[int, int, int]
CONSTRAST_MIN = 1.43
LIGHTNESS_BUMP = 0.14
RGB_MAX = 255.0
IS_HORIZONTAL = (True, True, True)
IS_VERTICAL = (False, False, False)
FG = "FG"
BG = "BG"
BOTH = "BOTH"
H = 0
L = 1
S = 2

""" EQ Stream """
CHUNK = 256  # Samples: 1024,  512, 256, 128
RATE = 44100  # Equivalent to Human Hearing at 40 kHz
MIN_HZ = 50
MAX_HZ = 20000  # Commonly referenced upper limit for "normal" audio range
MAX_VOL = 200
BUFFER_FRAMES = 4
IS_HORIZONTAL = (True, True, True)
IS_VERTICAL = (False, False, False)
NUM_BARS = 16
BAR_HEIGHT = 32

""" Game of Life """
GRID_MARGIN = 10
GRID_HEIGHT = PANEL_HEIGHT + GRID_MARGIN * 2
GRID_WIDTH = PANEL_WIDTH * 2 + GRID_MARGIN * 2
RNG_RANGE = 100
INIT_CUTOFF = 50
ALIVE = 1
DEAD = 0
ALIVE_RGB = np.array(list(WHITE.rgb))
DEAD_RGB = np.array(list(BLACK.rgb))
ADD_NOISE = "ADD_NOISE"
RESET = "RESET"

""" Sports """
HOME = "home"
AWAY = "away"
HOCKEY = "hockey"
BASEBALL = "baseball"
FOOTBALL = "football"
LOGO_SIZE = 36
LOGO_URL = "https://a.espncdn.com/i/teamlogos"

""" All Games """
ABBRPADDING = 2
LEAGUEDEFAULT = "All"
ROTATETIME = 5.0


""" Weather """
HOURLY = "Hourly"
DAILY = "Daily"
ALERT = "Alert"
FORECAST_TYPE = [HOURLY, DAILY, ALERT]
CONDITION = [
    "clear-night",
    "cloudy",
    "fog",
    "hail",
    "lightning",
    "lightning-rainy",
    "partlycloudy",
    "partlycloudy-night",
    "pouring",
    "rainy",
    "snowy",
    "snowy-rainy",
    "sunny",
    "windy",
    "windy-variant",
    "exceptional",
]
SMALL = 16
BIG = 32
CONDITION_SIZE = [SMALL, BIG]
IMG_PATH = "../img/weather"
COMPASS = [
    "N",
    "NNE",
    "NE",
    "ENE",
    "E",
    "ESE",
    "SE",
    "SSE",
    "S",
    "SSW",
    "SW",
    "WSW",
    "W",
    "WNW",
    "NW",
    "NNW",
    "N",
]
TOTAL_DEGREES = 360.0
SECTION_DEGREES = 22.5
NUM_FORECASTS = 4
UTC = ZoneInfo("UTC")
LOCALTZ = ZoneInfo("localtime")
