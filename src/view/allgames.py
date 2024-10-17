from collections import deque, Counter
from time import perf_counter

from PIL import Image, ImageColor, ImageDraw

from constants import (
    ABBRPADDING,
    ALLGAMES,
    BG,
    LEAGUEDEFAULT,
    LEAGUE_COLORS,
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

        self.states_scroll = ScrollingText(
            font=FONT_5X8,
            color=WHITE,
            starting_x=ABBRPADDING,
            y=(2 * FONT_5X8.height) + ABBRPADDING,
            left_bound=ABBRPADDING,
            right_bound=PANEL_WIDTH,
            num_spaces=1,
            speed=0.02,
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
        row_height = FONT_4X6.height + (2 * ABBRPADDING)
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

        y = y + FONT_4X6.height + ABBRPADDING
        DrawText(
            canvas,
            FONT_4X6,
            x + ABBRPADDING,
            y,
            ColorRGB(*txt),
            abbr,
        )
        DrawText(
            canvas,
            FONT_4X6,
            x + ABBRPADDING + middle,
            y,
            WHITE,
            f"{score}",
        )

    def draw_game(self, canvas, x, y, game):
        row_height = FONT_4X6.height + (2 * ABBRPADDING)
        top = 0
        left = 0
        bottom = row_height * 2
        right = PANEL_WIDTH

        team_width = int(PANEL_WIDTH / 2)

        background = Image.new("RGB", (PANEL_WIDTH, row_height * 2), BLACK.rgb)
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

        clock_x = x + ABBRPADDING
        clock_y = y + FONT_4X6.height + ABBRPADDING
        DrawText(canvas, FONT_4X6, clock_x, clock_y, WHITE, clock)

        y += row_height
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
        num_games = 5

        offset = self.offset
        league_filter = data.all_games["league_filter"]
        state_filter = data.all_games["state_filter"]
        games = data.all_games["games"].values()
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

        league_x = ABBRPADDING
        league_y = FONT_5X8.height
        DrawText(canvas, FONT_5X8, league_x, league_y, WHITE, self.league)

        all_states = f"No games for league: {self.league} state: {state_filter}  "
        if games:
            states = Counter([game["state"] for game in games])
            all_states = " ".join(
                [f"{state}: {count}" for state, count in sorted(states.items())]
            )

        self.states_scroll.draw(canvas, all_states)

        x = 0
        y = 21
        for i, game in enumerate(games[:num_games]):
            if i == 2:
                x = PANEL_WIDTH
                y = 1
            y += self.draw_game(canvas, x, y, game)
