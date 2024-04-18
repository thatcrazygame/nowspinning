import colorsys
import logging
from typing_extensions import Literal

import numpy as np
from PIL import Image
import wcag_contrast_ratio as contrast

from constants import (
    BG,
    BOTH,
    CONSTRAST_MIN,
    FG,
    IS_HORIZONTAL,
    IS_VERTICAL,
    LIGHTNESS_BUMP,
    RGB,
    RGB_MAX,
    H,
    S,
    L,
)
from constants.colors import BLACK, WHITE


logger = logging.getLogger(__name__)


def _normalize(rgb_component: int | float) -> float:
    return float(rgb_component) / RGB_MAX


def _unnormalize(rgb_component: float) -> int:
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


def _rgb_to_hls(color: RGB):
    normal = normalize_rgb(color)
    return colorsys.rgb_to_hls(*normal)


def get_min_contrast_fg_bg(fg: RGB, bg: RGB, adjust_first=BOTH) -> tuple[RGB, RGB]:
    f_h, f_l, f_s = _rgb_to_hls(fg)
    b_h, b_l, b_s = _rgb_to_hls(bg)
    bg_is_darker = b_l < f_l
    bg_lower_sat = b_s < f_s

    adjust = 0.01
    while not contrast.passes_AA(get_contrast(fg, bg)):
        f_h, f_l, f_s = _rgb_to_hls(fg)
        b_h, b_l, b_s = _rgb_to_hls(bg)

        at_max_or_min_lum = (bg_is_darker and (b_l == 0.0 or f_l == 1.0)) or (
            not bg_is_darker and (b_l == 1.0 or f_l == 0.0)
        )

        at_max_or_min_sat = (bg_lower_sat and (b_s == 0.0 or f_s == 1.0)) or (
            not bg_lower_sat and (b_s == 1.0 or f_s == 0.0)
        )

        if adjust_first is FG or adjust_first is BOTH or at_max_or_min_lum:
            fg = adjust_lightness(fg, adjust if bg_is_darker else adjust * -1)
        if adjust_first is BG or adjust_first is BOTH or at_max_or_min_lum:
            bg = adjust_lightness(bg, adjust * -1 if bg_is_darker else adjust)

        if adjust_first is FG or adjust_first is BOTH or at_max_or_min_sat:
            fg = adjust_saturation(fg, adjust if bg_is_darker else adjust * -1)
        if adjust_first is BG or adjust_first is BOTH or at_max_or_min_sat:
            bg = adjust_saturation(bg, adjust * -1 if bg_is_darker else adjust)

    return fg, bg


def normalize_rgb(color: RGB) -> tuple[float, float, float]:
    return tuple(_normalize(c) for c in color)


def get_contrast(color: RGB, background=BLACK.rgb) -> float:
    normalized_color = normalize_rgb(color)
    normalized_background = normalize_rgb(background)
    return contrast.rgb(normalized_background, normalized_color)


def adjust_hls_part(color: RGB, part, amount) -> RGB:
    if part not in [H, L, S]:
        return color

    hls = list(_rgb_to_hls(color))
    if amount > 0:
        hls[part] = min(hls[part] + amount, 1.0)
    else:
        hls[part] = max(hls[part] + amount, 0.0)
    r, g, b = (_unnormalize(c) for c in colorsys.hls_to_rgb(*hls))
    return r, g, b


def adjust_hue(color: RGB, amount) -> RGB:
    return adjust_hls_part(color, H, amount)


def adjust_lightness(color: RGB, amount=LIGHTNESS_BUMP) -> RGB:
    return adjust_hls_part(color, L, amount)


def adjust_saturation(color: RGB, amount) -> RGB:
    return adjust_hls_part(color, S, amount)


def _get_gradient_2d(start, stop, width, height, is_horizontal):
    if is_horizontal:
        return np.tile(np.linspace(start, stop, width), (height, 1))
    else:
        return np.tile(np.linspace(start, stop, height), (width, 1)).T


def _get_gradient_3d(width, height, start_list, stop_list, is_horizontal_list):
    result = np.zeros((height, width, len(start_list)), dtype=np.float64)

    gradient_components = enumerate(zip(start_list, stop_list, is_horizontal_list))
    for i, (start, stop, is_horizontal) in gradient_components:
        result[:, :, i] = _get_gradient_2d(start, stop, width, height, is_horizontal)

    return result


def get_gradient_img(
    width, height, colors: RGB | list[RGB] = None, direction=IS_VERTICAL
) -> Image.Image:
    one_color: RGB = None
    if type(colors) is list and len(colors) == 1:
        colors = colors[0]

    if type(colors) is RGB and len(colors) == 3:
        one_color = colors

    if colors is None or not (type(colors) is list or type(colors) is RGB):
        one_color = WHITE.rgb

    if one_color is not None:
        return Image.new("RGB", (width, height), one_color)

    num_gradients = len(colors) - 1
    gradient_height, extra = divmod(height, num_gradients)
    gradient_array = None
    for i in range(num_gradients):
        if i == num_gradients - 1:
            gradient_height += extra

        gradient = _get_gradient_3d(
            width, gradient_height, colors[i + 1], colors[i], direction
        )
        if gradient_array is None:
            gradient_array = gradient
        else:
            gradient_array = np.concatenate((gradient, gradient_array))

    with np.errstate(invalid="ignore"):
        np_array = np.uint8(gradient_array)
        return Image.fromarray(np_array)
