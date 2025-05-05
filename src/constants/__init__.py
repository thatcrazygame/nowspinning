import numpy as np
from constants.colors import BLACK, CRIMSON, PITTSGOLD, ROYALBLUE, WHITE
from constants.secondaryinfo import SECONDARY_DEFAULT, RH, SecondaryInfo, POP
from zoneinfo import ZoneInfo


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
FLAPPYBIRD = "Flappy Bird"
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
# (<num of freq. bins to put into bar bin>, <vol. weight multiplier>)
BIN_DIMENSIONS = [
    (1, 0.6),
    (1, 0.7),
    (1, 0.8),
    (1, 0.85),
    (2, 0.9),
    (2, 1.0),
    (2, 1.0),
    (2, 1.0),
    (4, 1.0),
    (4, 1.0),
    (4, 1.05),
    (4, 1.1),
    (4, 1.1),
    (8, 1.1),
    (8, 1.2),
    (16, 1.4),
]
CHUNK = 256  # Samples: 1024,  512, 256, 128
RATE = 44100  # Equivalent to Human Hearing at 40 kHz
MIN_HZ = 50
MAX_HZ = 20000  # Commonly referenced upper limit for "normal" audio range
MAX_VOL = 40
BUFFER_FRAMES = 1
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
UNAVAILABLE = "UNAVAILABLE"
NOT_FOUND = "NOT_FOUND"
BYE = "BYE"
POST = "POST"
PRE = "PRE"
IN = "IN"
GAME_STATE = [UNAVAILABLE, NOT_FOUND, BYE, POST, PRE, IN]

""" All Games """
LEAGUEDEFAULT = "All"
ROTATETIME = 5.0
LEAGUE_COLORS = {
    "NHL": PITTSGOLD,
    "NFL": CRIMSON,
    "MLB": ROYALBLUE,
}

""" Weather """
HOURLY = "Hourly"
DAILY = "Daily"
ALERT = "Alert"
FORECAST_TYPE = [HOURLY, DAILY, ALERT]
SECONDARY_TYPE: dict[str, SecondaryInfo] = {}
SECONDARY_TYPE[SECONDARY_DEFAULT.name] = SECONDARY_DEFAULT
SECONDARY_TYPE[POP.name] = POP
SECONDARY_TYPE[RH.name] = RH

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
