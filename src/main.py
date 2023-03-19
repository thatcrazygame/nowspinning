import asyncio
from base64 import b64decode
from datetime import datetime
from io import BytesIO
import os
import sys
import textwrap
import time
import xml.etree.ElementTree as ET

from adafruit_sgp40 import SGP40
from adafruit_scd30 import SCD30
from board import I2C
from dbus_next.aio import MessageBus
from PIL import Image, ImageDraw, ImageFont
from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics

sys.path.append(os.path.abspath(os.path.dirname(__file__) + '/..'))

PANEL_WIDTH = 64
PANEL_HEIGHT = 64
LEFT = -1
RIGHT = 1
SCROLL_SPEED = 1

class Data:
    """Class to share data between async functions"""

    def __init__(self):
        self.music_last_updated = None
        self.artist = None
        self.title = None
        self.album = None
        self.image = None
        self.temperature = None
        self.humidity = None
        self.CO2 = None
        self.VOC = None
        self.raw_gas = None

    def refresh_music_data(self, metadata, height, width):
        if metadata:
            self.music_last_updated = time.time()
        if 'xesam:artist' in metadata:
            self.artist = metadata['xesam:artist'].value
        if 'xesam:title' in metadata:
            self.title = metadata['xesam:title'].value
        if 'xesam:album' in metadata:
            self.album = metadata['xesam:album'].value
        if 'mpris:artUrl' in metadata:
            art_str = metadata['mpris:artUrl'].value
            art_str = art_str.replace('data:image/jpeg;base64,', '')
            art_base64 = BytesIO(b64decode(art_str))
            art_image = Image.open(art_base64)
            art_image.thumbnail((width, height), Image.ANTIALIAS)
            self.image = art_image

    @property
    def temperature_f(self):
        if self.temperature is None:
            return None
        else:
            return (self.temperature * 1.8) + 32.0


async def matrix_loop(bus: MessageBus, matrix: RGBMatrix, data: Data):
    canvas = matrix.CreateFrameCanvas()

    font_5x8 = graphics.Font()
    font_5x8.LoadFont('../fonts/5x8.bdf')
    
    font_8x13 = graphics.Font()
    font_8x13.LoadFont('../fonts/8x13.bdf')
    
    white_text = graphics.Color(255, 255, 255)

    margin = 2
    linespace = 1
    char_width = font_5x8.CharacterWidth(ord('A'))
    max_chars = (PANEL_WIDTH - margin) // char_width


    offset = font_8x13.height + margin
    x = PANEL_WIDTH + margin
    y = offset
    
    title_x = x
    title_y = y
    title_dir = LEFT
    
    artist_x = x
    artist_y = y + font_8x13.height + linespace
    artist_dir = LEFT
    while bus.connected:
        canvas.Clear()
        
        music_timeout = 30
        last_updated = data.music_last_updated
        if (True or last_updated is not None 
                and time.time() - last_updated  < music_timeout):
            
            
            

            # offset = font_5x8.height + margin
            # song_info = ''
            # if data.title is not None and data.artist is not None:
            #     song_info = f'{data.title} - {", ".join(data.artist)}'

            # for line in textwrap.wrap(song_info, max_chars):
            #     x = (matrix.width / 2) + margin
            #     y = offset
            #     len = graphics.DrawText(canvas, font_5x8, x, y,
            #                             white_text, line)
            #     offset += font_5x8.height + linespace       
            
            
            if data.title is not None and data.artist is not None:
                
                title_len = graphics.DrawText(canvas, font_8x13,
                                              title_x, title_y, 
                                              white_text, data.title)
                
                artist_len = graphics.DrawText(canvas, font_8x13,
                                               artist_x, artist_y,
                                               white_text, 
                                               ", ".join(data.artist))
                
                title_len_diff = PANEL_WIDTH - title_len
                if title_len_diff < 0:
                    title_x = title_x + (title_dir * SCROLL_SPEED)
                    if title_x - PANEL_WIDTH <= title_len_diff:
                        title_dir = RIGHT
                        
                    if title_x >= PANEL_WIDTH + margin:
                        title_dir = LEFT
                
                artist_len_diff = PANEL_WIDTH - artist_len
                if artist_len_diff < 0:    
                    artist_x = artist_x + (artist_dir * SCROLL_SPEED)
                    if artist_x - PANEL_WIDTH <= artist_len_diff:
                        artist_dir = RIGHT
                    
                    if artist_x >= PANEL_WIDTH + margin:
                        artist_dir = LEFT
                        
            if data.image is not None:
                canvas.SetImage(data.image)
                
        else:
            now = datetime.now()
            x = margin
            y = font_8x13.height + margin
            graphics.DrawText(canvas, font_8x13, 0, y, white_text,
                              now.strftime('%I:%M'))
            
            y = y + font_8x13.height + margin
            graphics.DrawText(canvas, font_5x8, x, y, white_text,
                              now.strftime('%d/%m/%Y'))
            
            y = font_8x13.height + margin
            if data.temperature_f is not None:
                x = (matrix.width / 2) + margin
                graphics.DrawText(canvas, font_8x13, x, y, white_text,
                                f'{data.temperature_f:.1f}°F')
            
            if data.humidity is not None:
                y = y + font_5x8.height + margin
                graphics.DrawText(canvas, font_5x8, x, y, white_text,
                                f'Hum: {data.humidity:.1f}%')
            
            if data.CO2 is not None:
                y = y + font_5x8.height + margin
                graphics.DrawText(canvas, font_5x8, x, y, white_text,
                                f'CO2: {int(data.CO2)}ppm')
            
            if data.VOC is not None:
                y = y + font_5x8.height + margin
                graphics.DrawText(canvas, font_5x8, x, y, white_text,
                                f'VOC: {data.VOC}')

        canvas = matrix.SwapOnVSync(canvas)
        await asyncio.sleep(0.05)


async def air_loop(bus: MessageBus, matrix: RGBMatrix, data: Data,
                   i2c=I2C()):
    # I don't know why, but defining i2c within the function doesn't work
    # Better than a global I guess?
    sgp = SGP40(i2c)
    scd = SCD30(i2c)
    while bus.connected:
        # since the measurement interval is long (2+ seconds)
        # we check for new data before reading
        # the values, to ensure current readings.
        if scd.data_available:
            data.temperature = scd.temperature
            data.humidity = scd.relative_humidity
            data.CO2 = scd.CO2

        if data.temperature is not None and data.humidity is not None:
            data.VOC = sgp.measure_index(data.temperature, data.humidity)
            data.raw_gas = sgp.measure_raw(data.temperature, data.humidity)

            # for testing
            # print(f'T: {data.temperature_f:.2f}')
            # print(f'H: {data.humidity:.2f}')
            # print(f'C: {data.CO2:.2f}')
            # print(f'V: {data.VOC:.2f}')
            # print('--------------')

        # The voc algorithm expects a 1Hz sampling rate
        await asyncio.sleep(1)


def init_matrix():
    options = RGBMatrixOptions()
    options.rows = PANEL_WIDTH
    options.cols = PANEL_HEIGHT
    options.chain_length = 2
    options.parallel = 1
    options.hardware_mapping = 'adafruit-hat-pwm'
    options.gpio_slowdown = 2
    #options.pwm_lsb_nanoseconds = 50
    #options.brightness = 50
    #options.pwm_bits = 8
    # options.show_refresh_rate = True

    matrix = RGBMatrix(options=options)
    return matrix


async def init_mpris():
    os.environ['DBUS_SESSION_BUS_ADDRESS'] = 'unix:path=/run/user/1000/bus'
    bus = await MessageBus().connect()

    tree = ET.parse('mpris.xml')

    obj = bus.get_proxy_object('org.mpris.MediaPlayer2.SongRec',
                               '/org/mpris/MediaPlayer2',
                               tree.getroot())

    player = obj.get_interface('org.mpris.MediaPlayer2.Player')
    properties = obj.get_interface('org.freedesktop.DBus.Properties')

    return bus, player, properties


async def main():
    bus, player, properties = await init_mpris()
    matrix = init_matrix()

    data = Data()
    metadata = await player.get_metadata()
    data.refresh_music_data(metadata, matrix.height, matrix.height)

    async def on_prop_change(interface_name, changed_properties,
                             invalidated_properties):
        for changed, variant in changed_properties.items():
            if changed == 'Metadata':
                metadata = await player.get_metadata()
                data.refresh_music_data(metadata, matrix.height, matrix.height)

    properties.on_properties_changed(on_prop_change)

    await asyncio.gather(matrix_loop(bus, matrix, data),
                         air_loop(bus, matrix, data))
    await bus.wait_for_disconnect()

loop = asyncio.get_event_loop()
loop.run_until_complete(main())
