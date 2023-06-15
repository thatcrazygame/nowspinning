import asyncio

import numpy as np
from PIL import Image, ImageDraw
from rgbmatrix.graphics import Color, DrawText, Font
from scipy.signal import convolve2d

from constants import PANEL_HEIGHT, PANEL_WIDTH
from data import Data
from . import ViewDrawer

GRID_MARGIN = 10
GRID_HEIGHT = PANEL_HEIGHT + GRID_MARGIN * 2
GRID_WIDTH = PANEL_WIDTH * 2 + GRID_MARGIN * 2

RNG_RANGE = 100
INIT_CUTOFF = 50

ALIVE = 1
DEAD = 0
ALIVE_RGB = np.array([255, 255, 255])
DEAD_RGB = np.array([0, 0, 0])

ADD_NOISE = "ADD_NOISE"
RESET = "RESET"


class GameOfLife(ViewDrawer):
    def __init__(self) -> None:
        super().__init__()
        self.fonts = {}

        font_4x6 = Font()
        font_4x6.LoadFont("../fonts/4x6.bdf")
        self.fonts["4x6"] = font_4x6

        self.generation: int = 0
        self.grid_data = self.new_random_grid()

    def new_random_grid(self, cutoff=INIT_CUTOFF):
        rng = np.random.default_rng()

        random = rng.integers(low=0, high=RNG_RANGE, size=GRID_HEIGHT * GRID_WIDTH)

        arr = np.array([1 if x > cutoff else 0 for x in random])
        return np.reshape(arr, (GRID_HEIGHT, GRID_WIDTH))

    def get_display_grid(self):
        data = self.grid_data.copy().flatten()
        arr = np.array([ALIVE_RGB if cell == ALIVE else DEAD_RGB for cell in data])
        grid = np.reshape(arr, (GRID_HEIGHT, GRID_WIDTH, 3))
        return grid

    def get_neighbor_count_grid(self):
        kernel = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]])

        return np.asmatrix(convolve2d(self.grid_data, kernel, "same"))

    async def handle_commands(self, commands: asyncio.Queue):
        while not commands.empty():
            command = await commands.get()
            if command == RESET:
                self.grid_data = self.new_random_grid()
                self.generation = 0
            elif command == ADD_NOISE:
                noise = self.new_random_grid(cutoff=95)
                new_grid = (noise == ALIVE) | (self.grid_data == ALIVE)
                new_grid = np.asarray(new_grid.astype(int))
                self.grid_data = new_grid

    def tick(self):
        self.generation += 1
        neighbors = self.get_neighbor_count_grid()
        # new_grid = np.zeros_like(self.grid_data)
        new_grid = (neighbors == 3) | ((self.grid_data == ALIVE) & (neighbors == 2))
        new_grid = np.asarray(new_grid.astype(int))

        self.grid_data = new_grid

    def draw_gens_counter(self, canvas):
        gens_str = f"gen: {self.generation}"
        font = self.fonts["4x6"]
        char_width = 4
        padding = 2
        width = len(gens_str) * char_width + padding * 2
        height = font.height + padding * 2
        img = Image.new("RGB", (width, height), (0, 0, 0))
        canvas.SetImage(img)
        DrawText(canvas, font, padding, font.height, Color(45, 90, 224), gens_str)

    async def draw(self, canvas, data: Data):
        self.update_last_drawn()
        await self.handle_commands(data.game_of_life_commands)
        img = Image.fromarray(np.uint8(self.get_display_grid()))
        canvas.SetImage(img, -GRID_MARGIN, -GRID_MARGIN)
        if data.game_of_life_show_gens:
            self.draw_gens_counter(canvas)
        self.tick()
