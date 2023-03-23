import asyncio
from base64 import b64decode
from datetime import datetime
from io import BytesIO
import os
import RPi.GPIO as GPIO
import sys
import time
import xml.etree.ElementTree as ET

from adafruit_sgp40 import SGP40
from adafruit_scd30 import SCD30
from board import I2C
from dbus_next.aio import MessageBus
from PIL import Image, ImageDraw, ImageFont
from rgbmatrix import RGBMatrix, RGBMatrixOptions
from rgbmatrix.graphics import Color, DrawText, Font

from scrollingtext import ScrollingText

sys.path.append(os.path.abspath(os.path.dirname(__file__) + '/..'))

PANEL_WIDTH = 64
PANEL_HEIGHT = 64

LEFT = -1
RIGHT = 1
SCROLL_SPEED = 1

I2C = I2C()
FAN_PIN = 25
PWM_FREQ = 100
GPIO.setmode(GPIO.BCM)
GPIO.setup(FAN_PIN, GPIO.OUT, initial=GPIO.LOW)

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

    font_5x8 = Font()
    font_5x8.LoadFont('../fonts/5x8.bdf')
    
    font_8x13 = Font()
    font_8x13.LoadFont('../fonts/8x13.bdf')
    
    white_text = Color(255, 255, 255)

    margin = 2
    linespace = 1

    offset = font_8x13.height + margin
    x = PANEL_WIDTH + margin
    y = offset
    
    title_y = y
    artist_y = y + font_8x13.height + linespace
    
    title_scroll = ScrollingText(font_8x13, white_text, LEFT, SCROLL_SPEED,
                                 PANEL_WIDTH, PANEL_WIDTH*2, x, title_y)
    
    artist_scroll = ScrollingText(font_8x13, white_text, LEFT, SCROLL_SPEED,
                                  PANEL_WIDTH, PANEL_WIDTH*2, x, artist_y)
    while bus.connected:
        canvas.Clear()
        
        music_timeout = 30
        last_updated = data.music_last_updated
        if (last_updated is not None 
                and time.time() - last_updated  < music_timeout):
            
            title = data.title
            artist = data.artist
            if title is not None and artist is not None:
                artists = ", ".join(artist)

                title_scroll.update_text(title)
                title_scroll.draw(canvas)
                
                artist_scroll.update_text(artists)
                artist_scroll.draw(canvas)
            
            if data.image is not None:
                canvas.SetImage(data.image)
                
        else:
            now = datetime.now()
            x = margin
            y = font_8x13.height + margin
            DrawText(canvas, font_8x13, 0, y, white_text,
                     now.strftime('%I:%M'))
            
            y = y + font_8x13.height + margin
            DrawText(canvas, font_5x8, x, y, white_text,
                     now.strftime('%m/%d/%Y'))
            
            y = font_8x13.height + margin
            if data.temperature_f is not None:
                x = (matrix.width / 2) + margin
                DrawText(canvas, font_8x13, x, y, white_text,
                         f'{data.temperature_f:.1f}°F')
            
            if data.humidity is not None:
                y = y + font_5x8.height + margin
                DrawText(canvas, font_5x8, x, y, white_text,
                         f'Hum: {data.humidity:.1f}%')
            
            if data.CO2 is not None:
                y = y + font_5x8.height + margin
                DrawText(canvas, font_5x8, x, y, white_text,
                         f'CO2: {int(data.CO2)}ppm')
            
            if data.VOC is not None:
                y = y + font_5x8.height + margin
                DrawText(canvas, font_5x8, x, y, white_text, 
                         f'VOC: {data.VOC}')

        canvas = matrix.SwapOnVSync(canvas)
        await asyncio.sleep(0.05)


async def air_loop(bus: MessageBus, matrix: RGBMatrix, data: Data):
    sgp = SGP40(I2C)
    scd = SCD30(I2C)
    while bus.connected:
        # since the measurement interval is long (2+ seconds)
        # we check for new data before reading
        # the values, to ensure current readings.
        if scd.data_available:
            data.temperature = scd.temperature
            data.humidity = scd.relative_humidity
            data.CO2 = scd.CO2

        if data.temperature is not None and data.humidity is not None:
            voc = asyncio.to_thread(sgp.measure_index,
                                    data.temperature, data.humidity)
            gas = asyncio.to_thread(sgp.measure_raw,
                                    data.temperature, data.humidity)
            data.VOC = await voc
            data.raw_gas = await gas

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

    fan=GPIO.PWM(FAN_PIN, PWM_FREQ)
    fan_speed = 70
    fan.start(fan_speed)

    await asyncio.gather(matrix_loop(bus, matrix, data),
                         air_loop(bus, matrix, data))
    
    await bus.wait_for_disconnect()

if __name__ == "__main__":
    asyncio.run(main())