from constants import PANEL_HEIGHT, PANEL_WIDTH, NUM_BARS, BAR_HEIGHT
from constants.colors import WHITE
from constants.fonts import FONT_8X13
from data import Data
from scrollingtext import ScrollingText
from view.viewbase import View, register


@register
class Music(View):
    sort = 5

    def __init__(self) -> None:
        super().__init__()

        margin = 2
        linespace = 1

        offset = FONT_8X13.height + margin
        x = PANEL_WIDTH + margin
        y = offset

        title_y = y
        artist_y = y + FONT_8X13.height + linespace

        self.title_scroll = ScrollingText(
            font=FONT_8X13,
            color=WHITE,
            starting_x=x,
            y=title_y,
            left_bound=x,
            right_bound=PANEL_WIDTH * 2,
            num_spaces=3,
            pause_dur=2.0,
            speed=0.04,
        )

        self.artist_scroll = ScrollingText(
            font=FONT_8X13,
            color=WHITE,
            starting_x=x,
            y=artist_y,
            left_bound=x,
            right_bound=PANEL_WIDTH * 2,
            num_spaces=3,
            pause_dur=2.0,
            speed=0.04,
        )

    async def draw(self, canvas, data: Data):
        title = data.title
        artists = data.artists
        self.title_scroll.draw(canvas, title)
        self.artist_scroll.draw(canvas, artists)

        if data.album_art is not None:
            canvas.SetImage(data.album_art)

        if data.eq_stream.frame_buffer.any():
            data.eq_stream.draw_eq(
                canvas,
                x=PANEL_WIDTH,
                y=PANEL_HEIGHT - BAR_HEIGHT,
                num_bars=NUM_BARS,
                bar_width=int(PANEL_WIDTH / NUM_BARS),
                max_height=BAR_HEIGHT,
                colors=data.album_art_colors,
            )
