import os
import sys

from rgbmatrix.graphics import Font

file_path = os.path.abspath(__file__)
root_folder = os.path.abspath(os.path.dirname(os.path.dirname(file_path)))
sys.path.append(root_folder)


class MonoFont(Font):
    def __init__(self, font_path: str) -> None:
        super().__init__()
        self._char_width: int = None
        self._LoadFont(font_path)

    def _LoadFont(self, font_path: str) -> None:
        super().LoadFont(font_path)
        self._char_width = self.CharacterWidth(ord(" "))

    @property
    def char_width(self) -> int:
        return self._char_width


FONT_4x6 = MonoFont("../fonts/4x6.bdf")
FONT_5x8 = MonoFont("../fonts/5x8.bdf")
FONT_8x13 = MonoFont("../fonts/8x13.bdf")
FONT_10x20 = MonoFont("../fonts/10x20.bdf")
