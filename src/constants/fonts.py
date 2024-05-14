import os
import sys

from rgbmatrix.graphics import Font

file_path = os.path.abspath(__file__)
root_folder = os.path.abspath(os.path.dirname(os.path.dirname(file_path)))
sys.path.append(root_folder)


class MonoFont(Font):
    def __init__(self, font_path: str) -> None:
        super().__init__()
        super().LoadFont(font_path)

    def str_width(self, string: str) -> int:
        return sum([self.CharacterWidth(ord(char)) for char in string])


FONT_4x6 = MonoFont("../fonts/4x6.bdf")
FONT_5x8 = MonoFont("../fonts/5x8.bdf")
FONT_8x13 = MonoFont("../fonts/8x13.bdf")
FONT_9x18 = MonoFont("../fonts/9x18.bdf")
FONT_10x20 = MonoFont("../fonts/10x20.bdf")
