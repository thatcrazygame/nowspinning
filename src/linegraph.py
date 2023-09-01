import logging
from typing import Tuple

from PIL import Image, ImageDraw
from rgbmatrix.graphics import Color, DrawText, Font

from img_funcs import get_gradient_img, adjust_lightness

logger = logging.getLogger(__name__)


class LineGraph(object):
    def __init__(
        self,
        label: str,
        data: list[float] = [],
        units: str = "",
        round: int = 0,
        line_color: Tuple[int, int, int] = (255, 255, 255),
        fill_color: Tuple[int, int, int] = (0, 0, 0),
        background: Tuple[int, int, int] = (0, 0, 0),
    ) -> None:
        self.label: str = label
        self.data: list[float] = data
        self.units: str = units
        self.round: int = round
        self.data_space: int = 3
        self.height: int = 12
        self.fixed_min_val: float = None
        self.fixed_max_val: float = None
        self.line_color: Tuple[int, int, int] = line_color
        self.fill_color: Tuple[int, int, int] = fill_color
        self.background: Tuple[int, int, int] = background

    @property
    def width(self) -> int:
        return (len(self.data) - 1) * self.data_space + 1

    def get_scaled_data(self) -> list[int]:
        scaled = []
        non_zeros = [d for d in self.data if d != 0]
        if not non_zeros:
            return scaled

        min_val = min(non_zeros)
        if self.fixed_min_val:
            min_val = self.fixed_min_val
        max_val = max(self.data)
        if self.fixed_max_val:
            max_val = self.fixed_max_val
        if max_val - min_val == 0:
            return scaled

        for d in self.data:
            val = d
            if d == 0:
                val = min_val
            if self.fixed_min_val and d < self.fixed_min_val:
                val = self.fixed_min_val
            if self.fixed_max_val and d > self.fixed_max_val:
                val = self.fixed_max_val

            val = round(
                (val - min_val) / (max_val - min_val) * (self.height - 1)
            )  # coords 0 based
            scaled.append(val)
        return scaled

    def get_graph_img(self, data: list[float] = None) -> Image.Image:
        if data is not None:
            self.data = data

        size = (self.width, self.height)
        img = Image.new("RGB", size, self.background)
        if self.background != (0, 0, 0):
            darker = adjust_lightness(self.background, -0.125)
            img = get_gradient_img(self.width, self.height, [self.background, darker])

        draw = ImageDraw.Draw(img)

        points: list[Tuple[int, int]] = []
        x = 0
        y = 0

        points.append((x, y))
        scaled = self.get_scaled_data()
        for i, y in enumerate(scaled):
            points.append((x, y))
            if i < len(scaled) - 1:
                x += self.data_space
        points.append((x, 0))

        draw.polygon(points, fill=self.fill_color)
        # remove first and last points becase they
        # are the front and back lines of the graph
        points.pop(0)
        points.pop()
        # draw line on top of the polygon fill
        draw.line(points, fill=self.line_color)
        logger.debug(points)

        # y coordinates are top to bottom in PIL images
        img = img.transpose(method=Image.Transpose.FLIP_TOP_BOTTOM)

        return img

    def draw(self, canvas, font: Font, x: int, y: int, text_color: Color) -> None:
        if not self.data:
            return

        graph_x = x
        graph_y = y
        img = self.get_graph_img()
        if len(self.data) > 1:
            canvas.SetImage(img, graph_x, graph_y)

        txt_x = img.width + 2
        txt_y = graph_y + self.height - 1
        last_val = self.data[-1]
        label = f"{self.label}: {round(last_val, self.round)}{self.units}"
        DrawText(canvas, font, txt_x, txt_y, text_color, label)
