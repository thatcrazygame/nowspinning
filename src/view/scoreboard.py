from io import BytesIO
import logging
from math import floor

import asyncio
from PIL import Image, ImageDraw
from rgbmatrix.graphics import DrawLine, DrawText
import requests

from constants import (
    ALIGN_CENTER,
    HOME,
    AWAY,
    HOCKEY,
    BASEBALL,
    FOOTBALL,
    LOGO_SIZE,
    LOGO_URL,
    PANEL_HEIGHT,
    PANEL_WIDTH,
    GAME_STATE,
    NOT_FOUND,
    POST,
    PRE,
    IN,
)
from constants.colors import BLACK, WHITE, GRAY
from constants.fonts import FONT_5X8, FONT_8X13, FONT_10X20, MonoFont
from data import Data
from scrollingtext import ScrollingText

from view.viewbase import View, register

logger = logging.getLogger(__name__)


@register
class Scoreboard(View):
    sort = 4

    def __init__(self) -> None:
        super().__init__()

        self.play_scroll = ScrollingText(
            font=FONT_8X13,
            color=WHITE,
            starting_x=0,
            y=PANEL_HEIGHT - 3,
            left_bound=0,
            right_bound=PANEL_WIDTH * 2,
            num_spaces=3,
            scroll_speed=2,
            align=ALIGN_CENTER,
        )

        self.cached_bases: dict[str, Image.Image] = {}
        self.cached_logos: dict[str, Image.Image] = {}

    async def get_logo(self, url: str, size: tuple) -> Image.Image:
        url = url.lower()
        logo_img = self.cached_logos.get(url)
        if not logo_img:
            background = Image.new("RGBA", size, BLACK.rgb)
            response = await asyncio.to_thread(requests.get, url)
            if response.status_code == requests.codes.ok:
                img = Image.open(BytesIO(response.content))
                img.thumbnail(size, Image.Resampling.LANCZOS)
                img = Image.alpha_composite(background, img)
                img = img.convert("RGB")
                self.cached_logos[url] = img
                logo_img = img
            else:
                logger.warning(vars(response))

        return logo_img

    def get_logo_x(self, homeaway: str) -> int:
        if homeaway == HOME:
            return PANEL_WIDTH * 2 - LOGO_SIZE
        else:
            return 0

    def get_inside_logo_x(self, homeaway: str, width: int, padding: int = 0) -> int:
        if homeaway == HOME:
            return int(PANEL_WIDTH * 2 - LOGO_SIZE - padding - width)
        else:
            return int(LOGO_SIZE + padding)

    def get_middle_logo_x(self, homeaway: str, width: int) -> int:
        logo_x = self.get_logo_x(homeaway)
        x = logo_x + floor(LOGO_SIZE / 2) - floor(width / 2)
        return x

    def get_outer_x(self, homeaway: str, width: int, padding: int = 0):
        if homeaway == HOME:
            return PANEL_WIDTH * 2 - width - padding
        else:
            return 0 + padding

    def get_possession_homeaway(self, possession_id, team_id, team_homeaway) -> str:
        if not possession_id:
            return None

        homeaway_char = {
            HOME: "►",
            AWAY: "◄",
        }

        if possession_id == team_id:
            return homeaway_char[team_homeaway]
        else:
            # remove team's homeaway to be left with oppo's homeaway
            homeaway_char.pop(team_homeaway)
            return list(homeaway_char.values())[0]

    def draw_clock(
        self,
        canvas,
        clock: str,
        font: MonoFont,
        color,
        show_possession=False,
        possession_homeaway=None,
    ):
        if not clock:
            return

        if show_possession and possession_homeaway:
            if possession_homeaway == "◄":
                clock = f"{possession_homeaway} {clock}"
            elif possession_homeaway == "►":
                clock = f"{clock} {possession_homeaway}"

        clock_width = font.str_width(clock)
        x = int(PANEL_WIDTH - clock_width / 2)
        y = font.height
        DrawText(canvas, font, x, y, color, clock)

    async def draw_logos(self, canvas, data: Data, logo_y: int):
        game = data.selected_game
        league = game.get("league")
        team_abbr = game.get("team_abbr")
        oppo_abbr = game.get("opponent_abbr")
        team_homeaway = game.get("team_homeaway") or HOME
        oppo_homeaway = game.get("opponent_homeaway") or AWAY
        if not team_abbr and not league:
            return
        team_url = f"{LOGO_URL}/{league}/500-dark/scoreboard/{team_abbr}.png"
        logo_size = (LOGO_SIZE, LOGO_SIZE)

        team_img = await self.get_logo(team_url, logo_size)
        if not team_img:
            return

        team_img_x = self.get_logo_x(team_homeaway)
        canvas.SetImage(team_img, team_img_x, logo_y)

        if oppo_abbr:
            oppo_url = f"{LOGO_URL}/{league}/500-dark/scoreboard/{oppo_abbr}.png"
            oppo_img = await self.get_logo(oppo_url, logo_size)
            if not oppo_img:
                return
            oppo_img_x = self.get_logo_x(oppo_homeaway)
            canvas.SetImage(oppo_img, oppo_img_x, logo_y)
        else:
            league_url = game.get("league_logo")
            league_img = await self.get_logo(league_url, logo_size)
            if not league_img:
                return
            league_img_x = self.get_logo_x(AWAY)
            canvas.SetImage(league_img, league_img_x, logo_y)

    def draw_score(self, canvas, score, homeaway, font: MonoFont, color, score_y=24):
        if not score:
            return

        score_width = font.str_width(str(score))
        x = self.get_inside_logo_x(homeaway, score_width, padding=2)
        y = score_y
        DrawText(canvas, font, x, y, color, str(score))

    def draw_timeouts(
        self, canvas, homeaway, timeouts: int, max_timeouts: int, y: int = 27
    ):
        if not timeouts:
            return

        line_width = 3
        space = 3
        max_width = line_width * max_timeouts + space * (max_timeouts - 1)
        x = self.get_inside_logo_x(homeaway, max_width, padding=2)
        for _ in range(timeouts):
            DrawLine(canvas, x, y, x + line_width, y, WHITE)
            x = x + line_width + space

    def draw_shots_label(self, canvas, font: MonoFont, color, y=35):
        shots = "shots"
        shots_width = font.str_width(shots)
        x = int(PANEL_WIDTH - shots_width / 2)
        DrawText(canvas, font, x, y, color, shots)

    def draw_shots(self, canvas, shots, homeaway, font: MonoFont, color, shots_y=45):
        if not shots:
            return

        shots_width = font.str_width(str(shots))
        x = self.get_inside_logo_x(homeaway, shots_width, padding=2)
        y = shots_y
        DrawText(canvas, font, x, y, color, str(shots))

    def draw_bases(self, canvas, game):
        on_first = game.get("on_first") or False
        on_second = game.get("on_second") or False
        on_third = game.get("on_third") or False

        bases_bin = f"{int(on_third)}{int(on_second)}{int(on_first)}"
        bases_img_path = f"../img/bases/bases_{bases_bin}.png"
        bases_img = None
        if bases_img_path in self.cached_bases:
            bases_img = self.cached_bases[bases_img_path]
        else:
            bases_img = Image.open(bases_img_path)
            if not bases_img:
                return None
            bases_img = bases_img.convert("RGB")
            self.cached_bases[bases_img_path] = bases_img

        if not bases_img:
            return

        bases_x = LOGO_SIZE + 2
        bases_y = 29
        canvas.SetImage(bases_img, bases_x, bases_y)

    def draw_count(self, canvas, game, font, color, count_y=35):
        outs = game.get("outs") or 0
        balls = game.get("balls") or 0
        strikes = game.get("strikes") or 0

        x = PANEL_WIDTH + 3
        y = count_y
        count = f"{balls}-{strikes}"
        DrawText(canvas, font, x, y, color, count)

        MAX_OUTS = 3
        radius = 3
        out_space = 2
        x = PANEL_WIDTH + out_space
        y = count_y + radius
        for o in range(MAX_OUTS):
            out_size = radius * 2
            out = Image.new("RGB", (out_size, out_size))
            draw = ImageDraw.Draw(out)
            fill = BLACK.rgb
            if outs >= o + 1:
                fill = WHITE.rgb
            draw.ellipse(
                (0, 0, out_size - 1, out_size - 1), fill=fill, outline=WHITE.rgb
            )
            canvas.SetImage(out, x, y)
            x += out.width + out_space

    def draw_down_distance_yard(
        self, canvas, down_distance: str, font: MonoFont, color, y: int = 37
    ):
        if not down_distance:
            return

        down_distance = down_distance.replace("and", "&")
        at_separator = " at "
        at_yard: str = None
        if at_separator in down_distance:
            down_yard = down_distance.split(at_separator)
            down_distance = down_yard[0]
            at_yard = f"@ {down_yard[1]}"

        dd_width = font.str_width(down_distance)
        x = int(PANEL_WIDTH - dd_width / 2)
        DrawText(canvas, font, x, y, color, down_distance)

        if not at_yard:
            return

        yard_width = font.str_width(at_yard)
        x = int(PANEL_WIDTH - yard_width / 2)
        y += 10
        DrawText(canvas, font, x, y, color, at_yard)

    def draw_record(
        self, canvas, homeaway: str, record: str, font: MonoFont, color, y: int
    ):
        if not record:
            return

        record_width = font.str_width(record)
        x = 0
        if record_width > LOGO_SIZE:
            x = self.get_outer_x(homeaway, record_width, padding=1)
        else:
            x = self.get_middle_logo_x(homeaway, record_width)
        DrawText(canvas, font, x, y, color, record)

    async def draw(self, canvas, data: Data):
        self.update_last_drawn()

        game = data.selected_game
        if not game:
            return

        game_state = game["state"].upper()
        if game_state not in GAME_STATE:
            game_state = NOT_FOUND

        sport = game.get("sport")
        team_homeaway = game.get("team_homeaway") or HOME
        oppo_homeaway = game.get("opponent_homeaway") or AWAY

        clock = game.get("clock") or "No Game Available"

        show_possession = False
        possession_homeaway = None
        if sport == FOOTBALL:
            show_possession = True
            possession_id = game.get("possession")
            team_id = game.get("team_id")
            possession_homeaway = self.get_possession_homeaway(
                possession_id, team_id, team_homeaway
            )

        self.draw_clock(
            canvas,
            clock,
            FONT_5X8,
            WHITE,
            show_possession,
            possession_homeaway,
        )

        logo_y = FONT_5X8.height + 1
        await self.draw_logos(canvas, data, logo_y)

        if game_state in [PRE, POST]:
            team_record = game.get("team_record")
            oppo_record = game.get("opponent_record")
            series_summary = game.get("series_summary")

            y = logo_y + LOGO_SIZE + FONT_5X8.height + 2
            if series_summary:
                x = PANEL_WIDTH - floor(FONT_5X8.str_width(series_summary) / 2)
                DrawText(canvas, FONT_5X8, x, y, WHITE, series_summary)
            else:
                self.draw_record(canvas, team_homeaway, team_record, FONT_5X8, WHITE, y)
                self.draw_record(canvas, oppo_homeaway, oppo_record, FONT_5X8, WHITE, y)

        if game_state not in [IN, POST]:
            return

        score_y = 24
        team_color = WHITE
        oppo_color = WHITE
        if game_state == POST:
            score_y = 32
            team_winner = game.get("team_winner")
            if team_winner is not None and not team_winner:
                team_color = GRAY

            opponent_winner = game.get("opponent_winner")
            if opponent_winner is not None and not opponent_winner:
                oppo_color = GRAY

        team_score = game.get("team_score")
        self.draw_score(
            canvas, team_score, team_homeaway, FONT_10X20, team_color, score_y
        )

        oppo_score = game.get("opponent_score")
        self.draw_score(
            canvas, oppo_score, oppo_homeaway, FONT_10X20, oppo_color, score_y
        )

        if game_state != IN:
            return

        last_play = game.get("last_play")
        self.play_scroll.draw(canvas, last_play)

        if sport == HOCKEY:
            team_shots = game.get("team_shots_on_target")
            oppo_shots = game.get("opponent_shots_on_target")

            if team_shots and oppo_shots:
                self.draw_shots_label(canvas, FONT_5X8, WHITE)

            self.draw_shots(canvas, team_shots, team_homeaway, FONT_5X8, WHITE)
            self.draw_shots(canvas, oppo_shots, oppo_homeaway, FONT_5X8, WHITE)

        if sport == BASEBALL:
            self.draw_bases(canvas, game)
            self.draw_count(canvas, game, FONT_5X8, WHITE)

        if sport == FOOTBALL:
            down_distance_text = game.get("down_distance_text")
            self.draw_down_distance_yard(canvas, down_distance_text, FONT_5X8, WHITE)

            team_timeouts = game.get("team_timeouts")
            oppo_timeouts = game.get("opponent_timeouts")
            max_timeouts = 3
            self.draw_timeouts(canvas, team_homeaway, team_timeouts, max_timeouts)
            self.draw_timeouts(canvas, oppo_homeaway, oppo_timeouts, max_timeouts)
