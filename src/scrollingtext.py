from time import perf_counter

from rgbmatrix.graphics import DrawText

from constants import ALIGN_CENTER, ALIGN_LEFT, ALIGN_RIGHT, DIR_LEFT
from constants.colors import ColorRGB
from constants.fonts import MonoFont


class ScrollingText(object):
    def __init__(
        self,
        font: MonoFont,
        color: ColorRGB,
        starting_x: int,
        y: int,
        left_bound: int,
        right_bound: int,
        scroll_amount: int = 1,
        scroll_dir: int = DIR_LEFT,
        speed: float = 0.0,
        text: str = "",
        num_spaces: int = 1,
        pause_dur: float = 0.0,
        align=ALIGN_LEFT,
    ) -> None:
        self._font = font
        self._color = color
        self._scroll_dir = scroll_dir
        self._scroll_amount = scroll_amount
        self._speed = speed
        self._last_scrolled = perf_counter()
        self._left_bound = left_bound
        self._right_bound = right_bound
        self._num_spaces = num_spaces
        self._pause_dur = pause_dur
        self._pause_time: float = None
        self._text = None

        self.align = align
        self.starting_x = starting_x
        self.x = starting_x
        self.y = y
        self.text = text

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        if self._text != value:
            self.x = self.starting_x
            self.pause()

        self._text = value

        if self.fits_in_bounds:
            if self.align is ALIGN_LEFT:
                self.x = self._left_bound
            elif self.align is ALIGN_RIGHT:
                self.x = self._right_bound - self.text_width
            elif self.align is ALIGN_CENTER:
                self.x = (self.bound_width / 2) - (self.text_width / 2)

    @property
    def _space_width(self) -> int:
        return self._font.CharacterWidth(ord(" ")) * self._num_spaces

    @property
    def text_width(self) -> int:
        return self._font.str_width(self.text)

    @property
    def is_paused(self) -> bool:
        if self._pause_time is None:
            return False

        dur_elapsed = perf_counter() - self._pause_time > self._pause_dur
        if dur_elapsed:
            self.unpause()
        return not dur_elapsed

    @property
    def bound_width(self) -> int:
        return self._right_bound - self._left_bound

    @property
    def fits_in_bounds(self) -> bool:
        return self.bound_width >= self.text_width

    @property
    def is_out_of_bounds(self) -> bool:
        offset = self._scroll_dir * (self.x - self._left_bound)
        return offset >= self.text_width + self._space_width

    def pause(self, pause_dur: float = None) -> None:
        self._pause_time = perf_counter()
        if pause_dur is not None:
            self._pause_dur = pause_dur

    def unpause(self) -> None:
        self._pause_time = None

    def draw(self, canvas, text: str = None) -> None:
        self.text = text

        if self.text is None or self.text.isspace():
            return

        DrawText(canvas, self._font, self.x, self.y, self._color, self.text)

        if self.fits_in_bounds:
            return

        x_2 = self.x - self._scroll_dir * (self.text_width + self._space_width)

        DrawText(canvas, self._font, x_2, self.y, self._color, self.text)

        if not self.is_paused and perf_counter() - self._last_scrolled >= self._speed:
            self.x += self._scroll_dir * self._scroll_amount
            self._last_scrolled = perf_counter()

        if self.is_out_of_bounds:
            self.x = self._left_bound
            self.pause()
