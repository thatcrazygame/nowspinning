import sys
import os

sys.path.append(os.path.abspath(os.path.dirname(__file__) + '/..'))

import xml.etree.ElementTree as ET
from dbus_next.aio import MessageBus
import asyncio
from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import base64
import textwrap

class Metadata:
    def __init__(self):
        self.artist = None
        self.title = None
        self.album = None
        self.image = None

    def refresh_music_data(self, metadata, height, width):
        if 'xesam:artist' in metadata:
            self.artist = metadata['xesam:artist'].value
        if 'xesam:title' in metadata:
            self.title = metadata['xesam:title'].value
        if 'xesam:album' in metadata:
            self.album = metadata['xesam:album'].value
        if 'mpris:artUrl' in metadata:
            art_str = metadata['mpris:artUrl'].value
            art_str = art_str.replace('data:image/jpeg;base64,','')
            art_base64 = BytesIO(base64.b64decode(art_str))
            art_image = Image.open(art_base64)
            art_image.thumbnail((width, height), Image.ANTIALIAS)
            self.image = art_image

async def matrix_loop(bus, matrix, meta):
    canvas = matrix.CreateFrameCanvas()

    font = graphics.Font()
    font.LoadFont('../fonts/5x8.bdf')
    textColor = graphics.Color(255, 255, 255)

    margin = 2
    linespace = 1
    max_chars = ((matrix.width / 2) - margin) // font.CharacterWidth(ord('A'))

    while bus.connected:
        canvas.Clear()
        if meta.image is not None:
            canvas.SetImage(meta.image)

        offset = font.height + margin
        song_info = ''
        if meta.title is not None and meta.artist is not None:
            song_info = f'{meta.title} - {", ".join(meta.artist)}'

        for line in textwrap.wrap(song_info, max_chars):
            len = graphics.DrawText(canvas, font, (matrix.width / 2) + margin, offset, textColor, line)
            offset += font.height + linespace

        #text_image = Image.new("RGB", (64,64))
        #draw = ImageDraw.Draw(text_image)
        #font = ImageFont.load('4x6.bdf')
        #draw.text((1,1), song_info, font=font, fill='#ffffff')
        #canvas.SetImage(text_image, 64, 0)

        canvas = matrix.SwapOnVSync(canvas)
        await asyncio.sleep(.2)

async def main():
    os.environ['DBUS_SESSION_BUS_ADDRESS'] = 'unix:path=/run/user/1000/bus'
    bus = await MessageBus().connect()

    tree = ET.parse('mpris.xml')
    obj = bus.get_proxy_object('org.mpris.MediaPlayer2.SongRec', '/org/mpris/MediaPlayer2', tree.getroot())
    player = obj.get_interface('org.mpris.MediaPlayer2.Player')
    properties = obj.get_interface('org.freedesktop.DBus.Properties')

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
    options.show_refresh_rate = True

    matrix = RGBMatrix(options = options)

    meta = Metadata()
    data = await player.get_metadata()
    meta.refresh_music_data(data, matrix.height, matrix.height)

    async def on_prop_change(interface_name, changed_properties, invalidated_properties):
        for changed, variant in changed_properties.items():
            if changed == 'Metadata':
                data = await player.get_metadata()
                meta.refresh_music_data(data, matrix.height, matrix.height)

    properties.on_properties_changed(on_prop_change)

    await asyncio.gather(matrix_loop(bus, matrix, meta))
    await bus.wait_for_disconnect()

loop = asyncio.get_event_loop()
loop.run_until_complete(main())
