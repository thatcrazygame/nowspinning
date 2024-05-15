import asyncio
from time import perf_counter

import numpy as np
from PIL import Image, ImageDraw
from rgbmatrix.graphics import DrawText
from scipy.signal import convolve2d

from constants import (
    GAMEOFLIFE,
    GRID_MARGIN,
    GRID_HEIGHT,
    GRID_WIDTH,
    RNG_RANGE,
    INIT_CUTOFF,
    ALIVE,
    DEAD,
    ALIVE_RGB,
    DEAD_RGB,
    ADD_NOISE,
    RESET,
)
from constants.fonts import FONT_4X6
from constants.colors import BLACK, ROYALBLUE, WHITE
from data import Data
from view.viewbase import View, register


@register
class GameOfLife(View):
    name: str = GAMEOFLIFE
    sort = 6

    def __init__(self) -> None:
        super().__init__()
        self.generation: int = 0
        self.grid_data = self.new_random_grid()
        self.last_tick = perf_counter()

    @property
    def alive_cells(self) -> int:
        return self.grid_data.sum()

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
        kernel = np.array(
            [
                [1, 1, 1],
                [1, 0, 1],
                [1, 1, 1],
            ]
        )

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
        self.last_tick = perf_counter()

    def draw_gens_counter(self, canvas):
        gens_str = f"gen: {self.generation}"
        font = FONT_4X6
        char_width = 4
        padding = 2
        width = len(gens_str) * char_width + padding * 2
        height = font.height + padding * 2
        img = Image.new("RGB", (width, height), BLACK.rgb)
        canvas.SetImage(img)
        DrawText(canvas, font, padding, font.height, ROYALBLUE, gens_str)

    async def draw(self, canvas, data: Data):
        self.update_last_drawn()
        await self.handle_commands(data.game_of_life_commands)

        img = Image.fromarray(np.uint8(self.get_display_grid()))
        canvas.SetImage(img, -GRID_MARGIN, -GRID_MARGIN)

        if data.game_of_life_show_gens:
            self.draw_gens_counter(canvas)

        data.game_of_life_generations = self.generation
        data.game_of_life_cells = self.alive_cells

        if perf_counter() - self.last_tick >= data.game_of_life_seconds_per_tick:
            self.tick()
