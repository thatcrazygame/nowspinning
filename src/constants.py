from enum import Enum

class View(Enum):
    OFF = 0
    DASHBOARD = 1
    MUSIC = 2
    SPORTS = 3


class GameState(Enum):
    # values represent priority, not chronological order
    NOT_FOUND = 0
    BYE = 1
    POST = 2
    PRE = 3
    IN = 4


PANEL_WIDTH = 64
PANEL_HEIGHT = 64