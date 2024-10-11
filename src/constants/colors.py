from rgbmatrix.graphics import Color


class ColorRGB(Color):
    def __init__(self, red: int, green: int, blue: int) -> None:
        super().__init__(red, green, blue)

    @property
    def rgb(self: Color):
        return (self.red, self.green, self.blue)


BLACK = ColorRGB(0, 0, 0)
WHITE = ColorRGB(255, 255, 255)
GRAY = ColorRGB(155, 155, 155)
CRIMSON = ColorRGB(191, 29, 0)
DARKRED = ColorRGB(51, 8, 0)
ROYALBLUE = ColorRGB(45, 90, 224)
COBALT = ColorRGB(0, 76, 191)
NAVY = ColorRGB(0, 20, 51)
SOFTGREEN = ColorRGB(109, 191, 119)
DARKGREEN = ColorRGB(29, 51, 32)
LIGHTGRAY = ColorRGB(187, 191, 172)
DARKSLATEGRAY = ColorRGB(50, 51, 46)
PITTSGOLD = ColorRGB(255, 182, 18)
