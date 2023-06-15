from PIL import Image, ImageDraw
from rgbmatrix.graphics import Color, DrawText, Font

from constants import PANEL_HEIGHT, PANEL_WIDTH, GameState
from constants.fonts import FONT_5x8, FONT_8x13, FONT_10x20, MonoFont
from data import Data
from scrollingtext import ScrollingText
from sports import League, Team
from . import ViewDrawer

HOME = "home"
AWAY = "away"
HOCKEY = "hockey"
BASEBALL = "baseball"
FOOTBALL = "football"
LOGO_SIZE = 40


class Scoreboard(ViewDrawer):
    def __init__(self) -> None:
        super().__init__()

        self.white_text = Color(255, 255, 255)

        self.play_scroll = ScrollingText(
            FONT_8x13,
            self.white_text,
            0,
            PANEL_HEIGHT - 2,
            0,
            PANEL_WIDTH * 2,
            num_spaces=3,
            scroll_speed=2,
        )

    def get_logo_x(self, homeaway: str) -> int:
        if homeaway == HOME:
            return PANEL_WIDTH * 2 - LOGO_SIZE
        else:
            return 0

    def get_score_x(self, homeaway: str, score: int, char_width: int) -> int:
        score_space = PANEL_WIDTH - LOGO_SIZE
        score_width = len(score) * char_width
        if homeaway == HOME:
            return int(PANEL_WIDTH + score_space / 2 - score_width / 2)
        else:
            return int(LOGO_SIZE + score_space / 2 - score_width / 2)

    def get_shots_x(self, homeaway: str, shots: str, char_width: int) -> int:
        if homeaway == HOME:
            shots_width = len(shots) * char_width
            return int(PANEL_WIDTH * 2 - LOGO_SIZE - char_width - shots_width)
        else:
            return int(LOGO_SIZE + char_width)

    def draw_clock(self, canvas, clock, font: MonoFont, color):
        if not clock:
            return

        clock_width = len(clock) * font.char_width
        x = int(PANEL_WIDTH - clock_width / 2)
        y = font.height
        DrawText(canvas, font, x, y, color, clock)

    def draw_logos(self, canvas, data: Data, team: Team, league: League, logo_y: int):
        attr = team.attributes
        team_homeaway = attr.get("team_homeaway") or HOME
        oppo_homeaway = attr.get("opponent_homeaway") or AWAY
        oppo_abbr = attr.get("opponent_abbr")

        logo_size = (LOGO_SIZE, LOGO_SIZE)
        team_img = team.get_logo(logo_size)
        if not team_img:
            return

        team_img_x = self.get_logo_x(team_homeaway)
        canvas.SetImage(team_img, team_img_x, logo_y)

        if oppo_abbr:
            oppo = data.sports[league.abbr].team(oppo_abbr)
            oppo_img = oppo.get_logo(logo_size)
            oppo_img_x = self.get_logo_x(oppo_homeaway)
            canvas.SetImage(oppo_img, oppo_img_x, logo_y)
        else:
            league_img = league.get_logo(logo_size)
            league_img_x = self.get_logo_x(AWAY)
            canvas.SetImage(league_img, league_img_x, logo_y)

    def draw_score(self, canvas, score, homeaway, font: MonoFont, color, score_y=25):
        if not score:
            return

        x = self.get_score_x(homeaway, score, font.char_width)
        y = score_y
        DrawText(canvas, font, x, y, color, score)

    def draw_shots_label(self, canvas, font: MonoFont, color, y=35):
        shots = "shots"
        shots_width = len(shots) * font.char_width
        x = int(PANEL_WIDTH - shots_width / 2)
        DrawText(canvas, font, x, y, color, shots)

    def draw_shots(self, canvas, shots, homeaway, font: MonoFont, color, shots_y=45):
        if not shots:
            return

        x = self.get_shots_x(homeaway, shots, font.char_width)
        y = shots_y
        DrawText(canvas, font, x, y, color, shots)

    def draw_bases(self, canvas, attributes):
        attr = attributes
        on_first = attr.get("on_first") or False
        on_second = attr.get("on_second") or False
        on_third = attr.get("on_third") or False

        bases_bin = f"{int(on_third)}{int(on_second)}{int(on_first)}"
        bases_img_file = f"../img/bases/bases_{bases_bin}.png"
        bases_img = Image.open(bases_img_file)
        bases_img = bases_img.convert("RGB")

        if not bases_img:
            return

        bases_x = LOGO_SIZE + 2
        bases_y = 30
        canvas.SetImage(bases_img, bases_x, bases_y)

    def draw_count(self, canvas, attributes, font, color, count_y=36):
        attr = attributes

        outs = attr.get("outs") or 0
        balls = attr.get("balls") or 0
        strikes = attr.get("strikes") or 0

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
            fill = (0, 0, 0)
            if outs >= o + 1:
                fill = (255, 255, 255)
            draw.ellipse(
                (0, 0, out_size - 1, out_size - 1), fill=fill, outline=(255, 255, 255)
            )
            canvas.SetImage(out, x, y)
            x += out.width + out_space

    def draw_last_play(self, canvas, last_play):
        if not last_play:
            return

        char_width = self.play_scroll._font.char_width
        play_width = len(last_play) * char_width
        play_x = PANEL_WIDTH - play_width / 2
        self.play_scroll._starting_x = play_x
        self.play_scroll.draw(canvas, last_play)

    async def draw(self, canvas, data: Data):
        self.update_last_drawn()

        league: League = None
        team: Team = None

        white_text = self.white_text

        if data.selected_league_abbr in data.sports:
            league = data.sports[data.selected_league_abbr]

        if league is not None and data.selected_team_abbr in league.teams:
            team = league.team(data.selected_team_abbr)

        if team is None:
            return

        attr = team.attributes
        sport = attr.get("sport")
        team_homeaway = attr.get("team_homeaway") or HOME
        oppo_homeaway = attr.get("opponent_homeaway") or AWAY

        clock = attr.get("clock")
        self.draw_clock(canvas, clock, FONT_5x8, white_text)

        logo_y = FONT_5x8.height + 2
        self.draw_logos(canvas, data, team, league, logo_y)

        if team.game_state not in [GameState.IN, GameState.POST]:
            return

        team_score = attr.get("team_score")
        self.draw_score(canvas, team_score, team_homeaway, FONT_10x20, white_text)

        oppo_score = attr.get("opponent_score")
        self.draw_score(canvas, oppo_score, oppo_homeaway, FONT_10x20, white_text)

        last_play = attr.get("last_play")
        self.draw_last_play(canvas, last_play)

        if team.game_state is not GameState.IN:
            return

        if sport == HOCKEY:
            team_shots = attr.get("team_shots_on_target")
            oppo_shots = attr.get("opponent_shots_on_target")

            if team_shots and oppo_shots:
                self.draw_shots_label(canvas, FONT_5x8, white_text)

            self.draw_shots(canvas, team_shots, team_homeaway, FONT_5x8, white_text)

            self.draw_shots(canvas, oppo_shots, oppo_homeaway, FONT_5x8, white_text)

        if sport == BASEBALL:
            self.draw_bases(canvas, attr)
            self.draw_count(canvas, attr, FONT_5x8, white_text)
