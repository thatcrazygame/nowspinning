from math import floor

from PIL import Image, ImageDraw
from rgbmatrix.graphics import Color, DrawLine, DrawText, Font

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
LOGO_SIZE = 36


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
        
        self.cached_bases: dict[str, Image.Image] = {}

    def get_logo_x(self, homeaway: str) -> int:
        if homeaway == HOME:
            return PANEL_WIDTH * 2 - LOGO_SIZE
        else:
            return 0

    def get_inside_logos_x(
        self, homeaway: str, text: str, char_width: int, padding: int = 0
    ) -> int:
        if homeaway == HOME:
            text_width = len(text) * char_width
            return int(PANEL_WIDTH * 2 - LOGO_SIZE - padding - text_width)
        else:
            return int(LOGO_SIZE + padding)

    def get_inside_logo_x(self, homeaway: str, width: int, padding: int = 0) -> int:
        if homeaway == HOME:
            return int(PANEL_WIDTH * 2 - LOGO_SIZE - padding - width)
        else:
            return int(LOGO_SIZE + padding)

    def get_middle_logo_x(self, homeaway: str, width: int) -> int:
        logo_x = self.get_logo_x(homeaway)
        x = logo_x + floor(LOGO_SIZE / 2) - floor(width / 2)
        return x

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

    def draw_score(self, canvas, score, homeaway, font: MonoFont, color, score_y=24):
        if not score:
            return

        score_width = len(str(score)) * font.char_width
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
            DrawLine(canvas, x, y, x + line_width, y, self.white_text)
            x = x + line_width + space

    def draw_shots_label(self, canvas, font: MonoFont, color, y=35):
        shots = "shots"
        shots_width = len(shots) * font.char_width
        x = int(PANEL_WIDTH - shots_width / 2)
        DrawText(canvas, font, x, y, color, shots)

    def draw_shots(self, canvas, shots, homeaway, font: MonoFont, color, shots_y=45):
        if not shots:
            return

        shots_width = len(str(shots)) * font.char_width
        x = self.get_inside_logo_x(homeaway, shots_width, padding=2)
        y = shots_y
        DrawText(canvas, font, x, y, color, str(shots))

    def draw_bases(self, canvas, attributes):
        attr = attributes
        on_first = attr.get("on_first") or False
        on_second = attr.get("on_second") or False
        on_third = attr.get("on_third") or False
        
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

    def draw_count(self, canvas, attributes, font, color, count_y=35):
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

        dd_width = len(down_distance) * font.char_width
        x = int(PANEL_WIDTH - dd_width / 2)
        DrawText(canvas, font, x, y, color, down_distance)

        if not at_yard:
            return

        yard_width = len(at_yard) * font.char_width
        x = int(PANEL_WIDTH - yard_width / 2)
        y += 10
        DrawText(canvas, font, x, y, color, at_yard)

    def draw_record(
        self, canvas, homeaway: str, record: str, font: MonoFont, color, y: int
    ):
        if not record:
            return

        record_width = len(record) * font.char_width
        x = self.get_middle_logo_x(homeaway, record_width)
        DrawText(canvas, font, x, y, color, record)

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

        show_possession = False
        possession_homeaway = None
        if sport == FOOTBALL:
            show_possession = True
            possession_id = attr.get("possession")
            team_id = attr.get("team_id")
            possession_homeaway = self.get_possession_homeaway(
                possession_id, team_id, team_homeaway
            )

        self.draw_clock(
            canvas,
            clock,
            FONT_5x8,
            white_text,
            show_possession,
            possession_homeaway,
        )

        logo_y = FONT_5x8.height + 1
        self.draw_logos(canvas, data, team, league, logo_y)

        if team.game_state in [GameState.PRE, GameState.POST]:
            team_record = attr.get("team_record")
            oppo_record = attr.get("opponent_record")
            y = logo_y + LOGO_SIZE + FONT_5x8.height + 2
            self.draw_record(
                canvas, team_homeaway, team_record, FONT_5x8, white_text, y
            )
            self.draw_record(
                canvas, oppo_homeaway, oppo_record, FONT_5x8, white_text, y
            )

        if team.game_state not in [GameState.IN, GameState.POST]:
            return

        team_score = attr.get("team_score")
        self.draw_score(canvas, team_score, team_homeaway, FONT_10x20, white_text)

        oppo_score = attr.get("opponent_score")
        self.draw_score(canvas, oppo_score, oppo_homeaway, FONT_10x20, white_text)

        if team.game_state is not GameState.IN:
            return

        last_play = attr.get("last_play")
        self.draw_last_play(canvas, last_play)

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

        if sport == FOOTBALL:
            down_distance_text = attr.get("down_distance_text")
            self.draw_down_distance_yard(
                canvas, down_distance_text, FONT_5x8, white_text
            )

            team_timeouts = attr.get("team_timeouts")
            oppo_timeouts = attr.get("opponent_timeouts")
            max_timeouts = 3
            self.draw_timeouts(canvas, team_homeaway, team_timeouts, max_timeouts)
            self.draw_timeouts(canvas, oppo_homeaway, oppo_timeouts, max_timeouts)
