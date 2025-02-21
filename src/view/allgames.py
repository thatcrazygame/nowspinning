from collections import deque, Counter
from time import perf_counter

from PIL import Image, ImageColor, ImageDraw

from constants import (
    ALLGAMES,
    ALIGN_CENTER,
    BG,
    LEAGUEDEFAULT,
    LEAGUE_COLORS,
    NOT_FOUND,
    PANEL_HEIGHT,
    PANEL_WIDTH,
    ROTATETIME,
)
from constants.colors import BLACK, ColorRGB, GRAY, WHITE
from constants.fonts import FONT_4X6, FONT_5X8
from data import Data
from view.viewbase import View, register
from rgbmatrix.graphics import DrawText
from scrollingtext import ScrollingText
from utils.images import get_contrast, get_min_contrast_fg_bg, CONSTRAST_MIN


@register
class AllGames(View):
    name = ALLGAMES
    sort = 3

    def __init__(self) -> None:
        super().__init__()

        self.offset = 0
        self.last_rotate = perf_counter()
        self.league = LEAGUEDEFAULT

        self.filter_scroll = ScrollingText(
            font=FONT_5X8,
            color=WHITE,
            starting_x=2,
            y=PANEL_HEIGHT - 3,
            left_bound=2,
            right_bound=PANEL_WIDTH * 2,
            speed=0.02,
            align=ALIGN_CENTER,
            num_spaces=3,
        )

    def get_colors(self, team_colors: list[str]):
        background = ImageColor.getcolor(team_colors[0], "RGB")
        outline = background
        txt = ImageColor.getcolor(team_colors[1], "RGB")
        txt, background = get_min_contrast_fg_bg(fg=txt, bg=background, adjust_first=BG)
        if get_contrast(outline) < CONSTRAST_MIN:
            outline = txt
        return background, txt, outline

    def draw_team(self, canvas, x, y, abbr, score, colors):
        bg, txt, outline = self.get_colors(colors)
        row_height = FONT_4X6.height + 3
        top = 0
        left = 0
        bottom = row_height
        right = int(PANEL_WIDTH / 2)
        middle = int(right / 2)

        img = Image.new("RGB", (right, row_height), BLACK.rgb)
        img_draw = ImageDraw.Draw(img)

        img_draw.rectangle(
            xy=[(left, top), (right - 1, bottom - 1)],
            fill=None,
            outline=outline,
        )
        img_draw.rectangle(
            xy=[(left, top), (middle - 1, bottom - 1)],
            fill=bg,
            outline=outline,
        )

        canvas.SetImage(img, x, y)

        y = y + FONT_4X6.height + 1
        DrawText(
            canvas,
            FONT_4X6,
            x + 2,
            y,
            ColorRGB(*txt),
            abbr,
        )
        DrawText(
            canvas,
            FONT_4X6,
            x + 2 + middle,
            y,
            WHITE,
            f"{score}",
        )

    def draw_game(self, canvas, x, y, game):
        row_height = 9
        top = 0
        left = 0
        bottom = row_height * 2 - 1
        right = PANEL_WIDTH

        team_width = int(PANEL_WIDTH / 2)

        background = Image.new("RGB", (PANEL_WIDTH, bottom), BLACK.rgb)
        background_draw = ImageDraw.Draw(background)

        league_color = WHITE
        if game.get("league") in LEAGUE_COLORS:
            league_color = LEAGUE_COLORS[game.get("league")]

        background_draw.polygon(
            xy=[(right, top), (right, top + 6), (right - 6, top)],
            fill=league_color.rgb,
            outline=league_color.rgb,
        )

        background_draw.rectangle(
            xy=[(left, top), (right - 1, bottom - 1)],
            fill=None,
            outline=GRAY.rgb,
        )

        canvas.SetImage(background, x, y)

        clock = (
            game.get("clock")
            .replace(" EDT", "")
            .replace(" EST", "")
            .replace("- ", "")
            .replace(" PM", "PM")
            .replace(" AM", "AM")
        )
        if "rain" in clock.lower():
            clock = "Rain Delay"
        if "postponed" in clock.lower():
            clock = "Postponed"
        if "delayed" in clock.lower():
            clock = "Delayed"

        clock_x = x + 2
        clock_y = y + FONT_4X6.height + 1
        DrawText(canvas, FONT_4X6, clock_x, clock_y, WHITE, clock)

        y += row_height - 1
        self.draw_team(
            canvas,
            x,
            y,
            game.get("away_abbr"),
            game.get("away_score"),
            game.get("away_colors"),
        )

        x += team_width
        self.draw_team(
            canvas,
            x,
            y,
            game.get("home_abbr"),
            game.get("home_score"),
            game.get("home_colors"),
        )

        return bottom

    async def draw(self, canvas, data: Data):
        if not data.all_games:
            return

        league_filter = data.all_games.get("league_filter")
        state_filter = data.all_games.get("state_filter")
        games = data.all_games.get("games")
        if not (league_filter and state_filter and games):
            return

        num_games = 6
        offset = self.offset

        games = games.values()
        if len(games) > num_games:
            games = deque(games)
            games.rotate(offset)
            if perf_counter() - self.last_rotate >= ROTATETIME:
                self.offset = (offset + num_games) % len(games)
                self.last_rotate = perf_counter()

        games = list(games)

        if league_filter != self.league:
            self.offset = 0
            self.last_rotate = perf_counter()
        self.league = league_filter

        x = 0
        y = 0
        for i, game in enumerate(games[:num_games]):
            if i == 3:
                x = PANEL_WIDTH
                y = 0
            y += self.draw_game(canvas, x, y, game)

        filter_txt = f"No games for league: {self.league} state: {state_filter}"
        all_states = ""
        if games:
            states = Counter([game["state"] for game in games])
            all_states = " ".join(
                [f"{state}: {count}" for state, count in sorted(states.items())]
            )
            all_states = all_states.replace(NOT_FOUND, "No Game")
            filter_txt = f"{self.league} - {all_states}"

        self.filter_scroll.draw(canvas, filter_txt)
