import colorsys
import logging

import numpy as np
from PIL import Image
import wcag_contrast_ratio as contrast

RGB = tuple[float, float, float] | tuple[int, int, int]
CONSTRAST_MIN = 1.43
LIGHTNESS_BUMP = 0.14
RGB_MAX = 255.0
IS_HORIZONTAL = (True, True, True)
IS_VERTICAL = (False, False, False)

logger = logging.getLogger(__name__)


def __normalize(rgb_component: int | float) -> float:
    return float(rgb_component) / RGB_MAX


def __unnormalize(rgb_component: float) -> int:
    return int(min(RGB_MAX, round(rgb_component * RGB_MAX)))


def get_dominant_colors(pil_img: Image.Image, palette_size=3) -> list[RGB]:
    img = pil_img.copy()
    # Reduce colors (uses k-means internally)
    paletted = img.convert("P", palette=Image.ADAPTIVE, colors=palette_size)
    # Find the color that occurs most often
    palette = paletted.getpalette()
    color_counts = sorted(paletted.getcolors(), reverse=True)

    # palette is a byte array of the colors in form [RGBRGBRGB...]
    colors = np.reshape(palette, (-1, 3))[:palette_size]
    colors = list(map(tuple, colors))
    # color_counts is a list of tuples: (count, index of color)
    # reorder colors to match the sorted counts
    colors = [colors[count[1]] for count in color_counts]

    return colors


def get_min_constrast_colors(colors: list[RGB]) -> list[RGB]:
    return [
        adjust_lightness(color) if get_contrast(color) < CONSTRAST_MIN else color
        for color in colors
    ]


def normalize_rgb(color: RGB) -> tuple[float, float, float]:
    return tuple(__normalize(c) for c in color)


def get_contrast(color: RGB, background=(0, 0, 0)) -> float:
    normalized_color = normalize_rgb(color)
    return contrast.rgb(background, normalized_color)


def adjust_lightness(color: RGB, amount=LIGHTNESS_BUMP) -> RGB:
    normalized_color = normalize_rgb(color)
    h, l, s = colorsys.rgb_to_hls(*normalized_color)
    l = min(l + amount, 1.0)
    r, g, b = (__unnormalize(c) for c in colorsys.hls_to_rgb(h, l, s))
    return r, g, b


def __get_gradient_2d(start, stop, width, height, is_horizontal):
    if is_horizontal:
        return np.tile(np.linspace(start, stop, width), (height, 1))
    else:
        return np.tile(np.linspace(start, stop, height), (width, 1)).T


def __get_gradient_3d(width, height, start_list, stop_list, is_horizontal_list):
    result = np.zeros((height, width, len(start_list)), dtype=np.float64)

    gradient_components = enumerate(zip(start_list, stop_list, is_horizontal_list))
    for i, (start, stop, is_horizontal) in gradient_components:
        result[:, :, i] = __get_gradient_2d(start, stop, width, height, is_horizontal)

    return result


def get_gradient_img(
    width, height, colors: RGB | list[RGB] = None, direction=IS_VERTICAL
) -> Image.Image:
    one_color: RGB = None
    if type(colors) is list and len(colors) == 1:
        colors = colors[0]

    if type(colors) is RGB and len(colors) == 3:
        one_color = colors

    if colors is None:
        one_color = (255, 255, 255)

    if one_color is not None:
        return Image.new("RGB", (width, height), one_color)

    num_gradients = len(colors) - 1
    gradient_height, extra = divmod(height, num_gradients)
    gradient_array = None
    for i in range(num_gradients):
        if i == num_gradients - 1:
            gradient_height += extra

        gradient = __get_gradient_3d(
            width, gradient_height, colors[i + 1], colors[i], direction
        )
        if gradient_array is None:
            gradient_array = gradient
        else:
            gradient_array = np.concatenate((gradient, gradient_array))

    with np.errstate(invalid="ignore"):
        np_array = np.uint8(gradient_array)
        return Image.fromarray(np_array)
