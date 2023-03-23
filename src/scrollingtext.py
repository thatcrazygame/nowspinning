# from rgbmatrix import RGBMatrix, RGBMatrixOptions
from rgbmatrix.graphics import Color, DrawText, Font

LEFT = -1
RIGHT = 1

class ScrollingText(object):
    def __init__(self, font: Font, color: Color, scroll_dir: int,
                 scroll_speed: int, left_bound: int, right_bound: int, 
                 starting_x: int, y: int, text: str = "") -> None:
        self._font = font
        self._color = color
        self._scroll_dir = scroll_dir
        self._scroll_speed = scroll_speed
        self._left_bound = left_bound
        self._right_bound = right_bound
        self._starting_x = starting_x
        
        self.x = starting_x
        self.y = y
        self.text = text
        
    def update_text(self, text: str):
        if text != self.text:
            self.x = self._starting_x
        self.text = text
        
    def draw(self, canvas):
        if self.text is not None and not self.text.isspace():
            text_len = DrawText(canvas, self._font, self.x, self.y, 
                                self._color, self.text)
            
            len_diff = self._right_bound - self._left_bound - text_len
            if len_diff < 0:
                x_2 = 0
                text_2 = ""
                scroll_dir = self._scroll_dir
                
                if scroll_dir == LEFT:
                    x_2 = self.x + text_len
                    text_2 = f" {self.text}"
                elif scroll_dir == RIGHT:
                    space_width = self._font.CharacterWidth(ord(" "))
                    x_2 = self.x - text_len - space_width
                    text_2 = f"{self.text} "
                
                text_2_len = DrawText(canvas, self._font,
                                      x_2, self.y, self._color,
                                      text_2)
                
                self.x += scroll_dir * self._scroll_speed
                
                reset_x = (self.x
                           + scroll_dir
                           * (self._left_bound - text_2_len))
                
                if (scroll_dir == LEFT and reset_x <= 0):
                    self.x = self._left_bound
                elif (scroll_dir == RIGHT and reset_x >= self._right_bound):
                    self.x = self._left_bound