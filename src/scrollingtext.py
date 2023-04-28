from enum import Enum

from rgbmatrix.graphics import Color, DrawText, Font

class Direction(Enum):
    LEFT = -1
    RIGHT = 1

class ScrollingText(object):
    def __init__(self, font: Font, color: Color, starting_x: int, y: int,
                 left_bound: int, right_bound: int, scroll_speed: int = 1, 
                 scroll_dir: Direction = Direction.LEFT, text: str = "",
                 num_spaces: int = 1) -> None:
        self._font = font
        self._color = color
        self._scroll_dir = scroll_dir.value
        self._scroll_speed = scroll_speed
        self._left_bound = left_bound
        self._right_bound = right_bound
        self._starting_x = starting_x
        self._num_spaces = num_spaces
        
        self.x = starting_x
        self.y = y
        self.text = text
        

    @property
    def __space_width(self) -> int:
        return self._font.CharacterWidth(ord(" ")) * self._num_spaces
 
  
    def _is_out_of_bounds(self) -> bool:
        offset = self._scroll_dir * (self.x - self._left_bound)
        return offset >= self.text_len + self.__space_width
 
        
    def update_text(self, text: str):
        if text != self.text:
            self.x = self._starting_x
        self.text = text
 
        
    def draw(self, canvas):
        if self.text is not None and not self.text.isspace():
            self.text_len = DrawText(canvas, self._font, self.x, self.y,
                                     self._color, self.text)
            
            len_diff = self._right_bound - self._left_bound - self.text_len
            if len_diff < 0:
                x_2 = (self.x 
                       - self._scroll_dir
                       * (self.text_len + self.__space_width))

                DrawText(canvas, self._font, x_2, self.y, self._color,
                         self.text)
                
                self.x += self._scroll_dir * self._scroll_speed

                if self._is_out_of_bounds():
                    self.x = self._left_bound