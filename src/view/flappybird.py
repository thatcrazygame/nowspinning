import asyncio
import math
import logging
from time import perf_counter
from typing import Dict, List, TypeAlias

import numpy as np
from PIL import Image, ImageDraw
from rgbmatrix.graphics import DrawText

from constants import FLAPPYBIRD, PANEL_HEIGHT, PANEL_WIDTH
from data import Data
from view.viewbase import View, register

logger = logging.getLogger(__name__)

Coords: TypeAlias = tuple[int, int, int, int]
PILColor: TypeAlias = float | tuple[float, ...] | str

SMALL = "SMALL"
MEDIUM = "MEDIUM"
LARGE = "LARGE"

READY = "READY"
PLAYING = "PLAYING"
PAUSED = "PAUSED"
GAME_OVER = "GAME OVER"

SPRITESHEET = "../img/flappy_sprites.png"
SPRITES: Dict[str, Coords] = {
    "TopTube": (368, 161, 380, 201),
    "BottomTube": (354, 161, 366, 201),
    "GetReady": (295, 59, 387, 84),
    "GameOver": (395, 59, 491, 80),
    "Ground": (304, 245, 448, 252),
    "Skyline": (337, 205, 475, 225),
    "Clouds": (149, 261, 429, 298),
}
BIRD_FRAMES: List[Coords] = [
    (383, 161, 394, 169),
    (396, 161, 407, 169),
    (409, 161, 420, 169),
    (396, 161, 407, 169),
]
DIGIT_SPRITES: Dict[str, List[Coords]] = {
    SMALL: [
        (137, 323, 143, 329),
        (137, 332, 143, 338),
        (137, 349, 143, 355),
        (137, 358, 143, 364),
        (137, 375, 143, 381),
        (137, 384, 143, 390),
        (137, 401, 143, 407),
        (137, 410, 143, 416),
        (137, 427, 143, 433),
        (137, 436, 143, 442),
    ],
    MEDIUM: [
        (136, 306, 144, 316),
        (138, 477, 144, 487),
        (136, 489, 144, 499),
        (130, 501, 138, 511),
        (501, 0, 509, 10),
        (501, 12, 509, 22),
        (504, 26, 512, 36),
        (504, 42, 512, 52),
        (292, 242, 300, 252),
        (310, 206, 318, 216),
    ],
    LARGE: [
        (495, 60, 507, 77),
        (323, 206, 331, 223),
        (291, 160, 303, 177),
        (305, 160, 317, 177),
        (319, 160, 331, 177),
        (333, 160, 345, 177),
        (291, 184, 303, 201),
        (305, 184, 317, 201),
        (319, 184, 331, 201),
        (333, 184, 345, 201),
    ],
}

FRAME_TIME = 1.0 / 90.0
FLAP = 75.0
GRAVITY = 350.0
GROUND_HEIGHT = 7

INIT_BIRD_X = 7
INIT_BIRD_Y = 6
FLAP_FRAME_TIME = 0.100

NUM_TUBES = 5
X_SPEED = 30.0
TUBE_GAP = 26
TUBE_WIDTH = 12
TUBE_SPACING = 40
NUM_LEVELS = 7
LEVEL_STEP = 4
MIN_TUBE_HEIGHT = 2
SCORE_X_THRESHOLD = -2

BACKGROUND: PILColor = (0, 139, 157, 255)


class Sprite(object):
    sprite_sheet = Image.open(SPRITESHEET)

    @classmethod
    def get_sprite(cls, coords: Coords) -> Image.Image:
        img = Sprite.sprite_sheet.crop(coords)
        return img

    def __init__(self, screen_buffer: Image.Image, x: float = 0, y: float = 0) -> None:
        self.sprite_sheet: Image.Image = None
        self.screen_buffer: Image.Image = screen_buffer
        self._img: Image.Image = None
        self.x: float = x
        self.y: float = y
        self.x_velocity: float = 0.0
        self.y_velocity: float = 0.0

    @property
    def img(self) -> Image.Image:
        return self._img

    @img.setter
    def img(self, value):
        self._img = value

    def update(self, frame_diff: float, game_state: str = None):
        pass

    def draw(self):
        if self.img is None:
            return

        self.screen_buffer.paste(
            self.img, (int(round(self.x)), int(round(self.y))), self.img
        )


class Bird(Sprite):
    def __init__(self, screen_buffer: Image.Image, x: float = 0, y: float = 0) -> None:
        self.radius = 4
        self.sprite_frame = 0
        self.sprites: List[Image.Image] = [
            Sprite.get_sprite(coords) for coords in BIRD_FRAMES
        ]
        self.frame_time = perf_counter()
        self.ground = float(PANEL_HEIGHT - GROUND_HEIGHT - self.img.height)
        super().__init__(screen_buffer, x, y)

    @property
    def img(self):
        self._img = self.sprites[self.sprite_frame]
        return self._img

    @property
    def y(self):
        return self._y

    @y.setter
    def y(self, value):
        sky = 0.0
        if value >= self.ground:
            self._y = self.ground
            self.y_velocity = 0.0
        elif value < sky:
            self._y = sky
            self.y_velocity = 0.0
        else:
            self._y = value

    @property
    def on_ground(self) -> bool:
        return self.y == self.ground

    def flap(self) -> None:
        self.y_velocity = FLAP

    def update(self, frame_diff: float, game_state: str):
        self.y_velocity = self.y_velocity - (GRAVITY * frame_diff)
        self.y = self.y - (self.y_velocity * frame_diff)
        flap_frame_diff = perf_counter() - self.frame_time
        if flap_frame_diff > FLAP_FRAME_TIME and game_state == PLAYING:
            self.sprite_frame = (self.sprite_frame + 1) % len(self.sprites)
            self.frame_time = perf_counter()


class Tube(Sprite):
    top: Image.Image = None
    bottom: Image.Image = None

    @classmethod
    def __init_tubes(cls):
        cls.top = Sprite.get_sprite(SPRITES["TopTube"])
        cls.bottom = Sprite.get_sprite(SPRITES["BottomTube"])

    def __init__(self, screen_buffer: Image.Image, x: float) -> None:
        if not Tube.top or not Tube.bottom:
            Tube.__init_tubes()

        self.height = PANEL_HEIGHT
        self.width = TUBE_WIDTH
        self.level = self.random_level()
        super().__init__(screen_buffer, x, 0)
        self.x_velocity = -50.0

    def random_level(self) -> int:
        return np.random.randint(0, NUM_LEVELS)

    @property
    def img(self):
        if self._img is None:
            self._img = Image.new("RGBA", (TUBE_WIDTH, PANEL_HEIGHT), (0, 0, 0, 0))
            self._img.paste(Tube.top, (0, self.top_level - Tube.top.height), Tube.top)
            self._img.paste(Tube.bottom, (0, self.bottom_level), Tube.bottom)

        return self._img

    @property
    def level(self):
        return self._level

    @level.setter
    def level(self, value):
        self._level = value
        self.top_level = MIN_TUBE_HEIGHT + (self._level * LEVEL_STEP)
        self.bottom_level = self.top_level + TUBE_GAP


class Digit(Sprite):
    def __init__(
        self, screen_buffer: Image.Image, x=0, y=0, d: int = 0, size: str = MEDIUM
    ) -> None:
        super().__init__(screen_buffer, x, y)
        if size not in DIGIT_SPRITES:
            self.size = MEDIUM
        else:
            self.size = size

        self._num: int = None
        self.num = d

    @property
    def img(self) -> Image.Image:
        if self.num is None:
            return None

        if self._img is None:
            coords = DIGIT_SPRITES[self.size][self.num]
            self._img = Sprite.get_sprite(coords)

        return self._img

    @property
    def num(self):
        return self._num

    @num.setter
    def num(self, value):
        try:
            value = int(value)
        except ValueError:
            value = None

        if value is not None and self._num is not None and value != self._num:
            self._img = None

        self._num = value


class Score(Digit):
    @property
    def img(self) -> Image.Image:
        if self.num is None:
            return None

        if self._img is None:
            digits = [
                Digit(self.screen_buffer, d=d, size=self.size) for d in str(self.num)
            ]

            height = max([d.img.height for d in digits])
            width = sum([d.img.width for d in digits])

            img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            x = 0
            y = 0
            for digit in digits:
                img.paste(digit.img, (x, y), digit.img)
                x += digit.img.width

            self._img = img

        return self._img

    def center_x(self):
        self.x = (PANEL_WIDTH / 2) - int(self.img.width / 2)


class Title(Sprite):
    def __init__(self, screen_buffer, x=0, y=0, coords: Coords = (0, 0, 0, 0)):
        super().__init__(screen_buffer, x, y)
        self.coords = coords
        self.center()

    @property
    def img(self) -> Image.Image:
        if self._img is None:
            self._img = Sprite.get_sprite(self.coords)
        return self._img

    def center(self):
        self.x = int(PANEL_WIDTH - (self.img.width / 2))
        self.y = int((PANEL_HEIGHT / 2) - (self.img.height / 2))


class EndlessScroll(Sprite):
    def __init__(
        self,
        screen_buffer,
        x=0,
        y=0,
        coords: Coords = (0, 0, 0, 0),
        speed_mult: float = 1.0,
    ):
        super().__init__(screen_buffer, x, y)
        self.coords = coords
        self.speed_mult = speed_mult

    @property
    def img(self) -> Image.Image:
        if self._img is None:
            sprite = Sprite.get_sprite(self.coords)
            img = Image.new("RGBA", (sprite.width * 2, sprite.height), (0, 0, 0, 0))
            img.paste(sprite, (0, 0), sprite)
            img.paste(sprite, (sprite.width, 0), sprite)
            self._img = img
        return self._img

    def update(self, frame_diff, game_state=None):
        self.x -= X_SPEED * self.speed_mult * frame_diff
        if self.x <= -1 * self.img.width / 2:
            self.x = 0


@register
class FlappyBird(View):
    name: str = FLAPPYBIRD
    sort = 7

    def __init__(self) -> None:
        super().__init__()
        self.last_frame = perf_counter()
        size = (PANEL_WIDTH * 2, PANEL_HEIGHT)
        self.screen_buffer = Image.new("RGBA", size, BACKGROUND)
        self._game_state = READY

        self.bird = Bird(self.screen_buffer, INIT_BIRD_X, INIT_BIRD_Y)
        self.tubes: List[Tube] = []

        self.score = Score(self.screen_buffer, x=PANEL_WIDTH / 2, y=5, d=0, size=MEDIUM)

        self.get_ready = Title(self.screen_buffer, coords=SPRITES["GetReady"])
        self.game_over = Title(self.screen_buffer, coords=SPRITES["GameOver"])

        self.ground = EndlessScroll(self.screen_buffer, coords=SPRITES["Ground"])
        self.ground.y = PANEL_HEIGHT - self.ground.img.height

        self.skyline = EndlessScroll(
            self.screen_buffer, coords=SPRITES["Skyline"], speed_mult=0.8
        )
        self.skyline.y = self.ground.y - self.skyline.img.height

        self.clouds = EndlessScroll(
            self.screen_buffer, coords=SPRITES["Clouds"], speed_mult=0.6
        )
        self.clouds.y = self.skyline.y - self.clouds.img.height

        self.new_game()

    def new_game(self):
        self.game_state = READY
        self.score.num = 0
        self.front_tube_x = PANEL_WIDTH
        self.tubes = []
        for i in range(NUM_TUBES):
            tube_x = self.front_tube_x + (i * TUBE_SPACING)
            tube = Tube(self.screen_buffer, tube_x)
            self.tubes.append(tube)
        self.bird.y = INIT_BIRD_Y

    @property
    def game_state(self):
        return self._game_state

    @game_state.setter
    def game_state(self, value):
        if value not in [READY, PLAYING, PAUSED, GAME_OVER]:
            value = PAUSED
        self._game_state_time = perf_counter()
        self._game_state = value

    @property
    def game_state_time(self):
        return self._game_state_time

    @property
    def time_since_game_state(self):
        return perf_counter() - self.game_state_time

    async def handle_commands(self, commands: asyncio.Queue):
        while not commands.empty():
            command = await commands.get()
            if command == "FLAP":
                if self.game_state in [READY, PAUSED]:
                    self.game_state = PLAYING
                elif self.game_state == GAME_OVER and self.time_since_game_state > 1.0:
                    self.new_game()
                elif self.game_state == PLAYING:
                    self.bird.flap()

    def clear_buffer(self):
        draw = ImageDraw.Draw(self.screen_buffer)
        draw.rectangle((0, 0, PANEL_WIDTH * 2, PANEL_HEIGHT), fill=BACKGROUND)

    def update_sprites(self, frame_diff):
        if self.game_state in [PLAYING, GAME_OVER]:
            self.bird.update(frame_diff, self.game_state)

        if self.game_state == PLAYING:
            old_x = self.front_tube_x
            self.front_tube_x -= X_SPEED * frame_diff
            new_x = self.front_tube_x

            self.score.center_x()
            if old_x > SCORE_X_THRESHOLD and new_x <= SCORE_X_THRESHOLD:
                self.score.num += 1

            for i, tube in enumerate(self.tubes):
                tube.x = self.front_tube_x + (i * TUBE_SPACING)

            if self.front_tube_x < -1 * TUBE_SPACING:
                self.front_tube_x += TUBE_SPACING
                del self.tubes[0]
                new_tube = Tube(self.screen_buffer, PANEL_WIDTH * 2)
                self.tubes.append(new_tube)

            self.ground.update(frame_diff)
            self.skyline.update(frame_diff)
            self.clouds.update(frame_diff)

    def draw_sprites(self):
        self.skyline.draw()
        self.clouds.draw()

        for tube in self.tubes:
            tube.draw()

        self.bird.draw()
        self.ground.draw()

        if self.game_state in [PLAYING, PAUSED, GAME_OVER]:
            self.score.draw()

        if self.game_state in [READY, PAUSED]:
            self.get_ready.draw()
        elif self.game_state == GAME_OVER:
            self.game_over.draw()

    def check_overlap(self, R, Xc, Yc, X1, Y1, X2, Y2) -> bool:
        # Find the nearest point on the rectangle to the center of the circle
        Xn = max(X1, min(Xc, X2))
        Yn = max(Y1, min(Yc, Y2))

        # Find the distance between the nearest point and the center of the circle
        # Distance between 2 points, (x1, y1) & (x2, y2) in 2D Euclidean space
        # is ((x1-x2)**2 + (y1-y2)**2)**0.5
        Dx = Xn - Xc
        Dy = Yn - Yc
        return (Dx**2 + Dy**2) <= R**2

    def collision_check(self) -> bool:
        collision = False
        r = self.bird.radius
        circle = (
            r,
            self.bird.x + r,
            self.bird.y + r,
        )
        self.message = ""

        for tube in self.tubes[:2]:
            front = tube.x
            back = tube.x + tube.width
            top = (front, 0, back, tube.top_level)
            bottom = (front, tube.bottom_level, back, PANEL_HEIGHT)

            top_overlap = self.check_overlap(*circle, *top)
            bottom_overlap = self.check_overlap(*circle, *bottom)

            if top_overlap or bottom_overlap:
                collision = True

        return collision or self.bird.on_ground

    def unload(self):
        super().unload()
        if self.game_state == PLAYING:
            self.game_state = PAUSED

    def load(self):
        super().load()
        if self.game_state == GAME_OVER:
            self.new_game()

    async def draw(self, canvas, data: Data):
        await self.handle_commands(data.flappy_bird_commands)

        frame_diff = perf_counter() - self.last_frame

        if frame_diff >= FRAME_TIME:
            self.update_sprites(frame_diff)
            self.clear_buffer()
            self.draw_sprites()
            if self.game_state == PLAYING:
                if self.collision_check():
                    self.game_state = GAME_OVER
            self.last_frame = perf_counter()

        canvas.SetImage(self.screen_buffer.convert("RGB"), 0, 0)
