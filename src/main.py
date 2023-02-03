import sys
import os
import xml.etree.ElementTree as ET
from dbus_next.aio import MessageBus
import asyncio
from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from base64 import b64decode
import textwrap
import board
from adafruit_sgp40 import SGP40
from adafruit_scd30 import SCD30

sys.path.append(os.path.abspath(os.path.dirname(__file__) + '/..'))


class Data:
    """Class to share data between async functions"""

    def __init__(self):
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
        return (self.temperature * 1.8) + 32.0


async def matrix_loop(bus: MessageBus, matrix: RGBMatrix, data: Data):
    canvas = matrix.CreateFrameCanvas()

    font = graphics.Font()
    font.LoadFont('../fonts/5x8.bdf')
    textColor = graphics.Color(255, 255, 255)

    margin = 2
    linespace = 1
    max_chars = ((matrix.width / 2) - margin) // font.CharacterWidth(ord('A'))

    while bus.connected:
        canvas.Clear()
        if data.image is not None:
            canvas.SetImage(data.image)

        offset = font.height + margin
        song_info = ''
        if data.title is not None and data.artist is not None:
            song_info = f'{data.title} - {", ".join(data.artist)}'

        for line in textwrap.wrap(song_info, max_chars):
            x = (matrix.width / 2) + margin
            y = offset
            len = graphics.DrawText(canvas, font, x, y, textColor, line)
            offset += font.height + linespace

        #text_image = Image.new("RGB", (64,64))
        #draw = ImageDraw.Draw(text_image)
        #font = ImageFont.load('4x6.bdf')
        # draw.text((1,1), song_info, font=font, fill='#ffffff')
        #canvas.SetImage(text_image, 64, 0)

        canvas = matrix.SwapOnVSync(canvas)
        await asyncio.sleep(.2)


async def air_loop(bus: MessageBus, matrix: RGBMatrix, data: Data,
                   i2c=board.I2C()):
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
            print(f'T: {data.temperature_f:.2f}')
            print(f'H: {data.humidity:.2f}')
            print(f'C: {data.CO2:.2f}')
            print(f'V: {data.VOC:.2f}')
            print('--------------')

        # The voc algorithm expects a 1Hz sampling rate
        await asyncio.sleep(1)


def init_matrix():
    options = RGBMatrixOptions()
    options.rows = 64
    options.cols = 64
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
