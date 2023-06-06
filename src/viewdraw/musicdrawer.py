from constants import PANEL_HEIGHT, PANEL_WIDTH
from data import Data
from rgbmatrix.graphics import Color, Font
from scrollingtext import ScrollingText
from . import ViewDrawer

NUM_BARS = 16
BAR_HEIGHT = 32

class MusicDrawer(ViewDrawer):
    def __init__(self) -> None:
        super().__init__()
        font_8x13 = Font()
        font_8x13.LoadFont("../fonts/8x13.bdf")
        
        white_text = Color(255, 255, 255)
        margin = 2
        linespace = 1

        offset = font_8x13.height + margin
        x = PANEL_WIDTH + margin
        y = offset
        
        title_y = y
        artist_y = y + font_8x13.height + linespace
        
        self.title_scroll = ScrollingText(font_8x13, white_text, x, title_y,
                                          PANEL_WIDTH, PANEL_WIDTH*2, 
                                          num_spaces=3, pause_dur=2.0)
        
        self.artist_scroll = ScrollingText(font_8x13, white_text, x, artist_y,
                                           PANEL_WIDTH, PANEL_WIDTH*2,
                                           num_spaces=3, pause_dur=2.0)
    
    async def draw(self, canvas, data: Data):
        self.update_last_drawn()
        
        title = data.title
        artist = data.artist
        if title is not None:
            self.title_scroll.draw(canvas, title)
            
        if artist is not None:
            artists = ", ".join(artist)
            self.artist_scroll.draw(canvas, artists)
            
        if data.album_art is not None:
            canvas.SetImage(data.album_art)

        if data.eq_stream.frame_buffer.any():
            data.eq_stream.draw_eq(canvas,
                                   x=PANEL_WIDTH, 
                                   y=PANEL_HEIGHT-BAR_HEIGHT,
                                   num_bars=NUM_BARS, 
                                   bar_width=int(PANEL_WIDTH/NUM_BARS),
                                   max_height=BAR_HEIGHT,
                                   colors=data.album_art_colors)
                
