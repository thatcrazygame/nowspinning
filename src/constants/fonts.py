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
        if string is None:
            return 0

        return sum([self.CharacterWidth(ord(char)) for char in string])


FONT_4X6 = MonoFont("../fonts/4x6.bdf")
FONT_5X8 = MonoFont("../fonts/5x8.bdf")
FONT_8X13 = MonoFont("../fonts/8x13.bdf")
FONT_9X18 = MonoFont("../fonts/9x18.bdf")
FONT_10X20 = MonoFont("../fonts/10x20.bdf")
