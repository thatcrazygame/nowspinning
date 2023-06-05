import asyncio
from base64 import b64decode
from datetime import datetime
from enum import Enum
from gpiozero import PWMOutputDevice
from io import BytesIO
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from adafruit_sgp40 import SGP40
from adafruit_scd30 import SCD30
from board import SCL, SDA
from busio import I2C
from dbus_next.aio import MessageBus
from dbus_next.errors import DBusError
from dotenv import load_dotenv
from ha_mqtt_discoverable import Settings, DeviceInfo, Discoverable, EntityInfo, Subscriber
import numpy as np
from paho.mqtt.client import Client, MQTTMessage
from PIL import Image, ImageChops, ImageDraw, ImageFont
from rgbmatrix import RGBMatrix, RGBMatrixOptions
from rgbmatrix.graphics import Color, DrawText, Font

import callbacks
from constants import View
from customdiscoverable import Select, SharedSensor
from eqstream import EQStream
from linegraph import LineGraph
from mqttdevice import MQTTDevice
from scrollingtext import ScrollingText
from sports import League, Team

sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/.."))

PANEL_WIDTH = 64
PANEL_HEIGHT = 64
# SCD-30 has tempremental I2C with clock stretching, datasheet recommends
# starting at 50KHz
I2C = I2C(SCL, SDA, frequency=50000)
FAN_PIN = 25
LOGO_SIZE = 40
NUM_BARS = 16

load_dotenv()

class Data(object):
    """Class to share data between async functions"""

    def __init__(self):
        self.music_last_updated = None
        self.artist = None
        self.title = "Listening..."
        self.album = None
        self.album_art = Image.open("../img/microphone.jpeg")
        self.album_art_colors = None
        self.temperature = None
        self.humidity = None
        self.co2 = None
        self.voc = None
        self.raw_gas = None
        self.averages: dict[str, list[float]] = {}
        self.view: View = View.SPORTS
        self.sports: dict[str, League] = {}
        self.selected_league_abbr: str = None
        self.selected_team_abbr: str = None
        self.switch_to_music: bool = False
    

    @property
    def temperature_f(self):
        if self.temperature is None:
            return None
        else:
            return (self.temperature * 1.8) + 32.0
        
    def get_dominant_colors(self, pil_img, palette_size=4):
        # Resize image to speed up processing
        img = pil_img.copy()
        # Reduce colors (uses k-means internally)
        paletted = img.convert('P', palette=Image.ADAPTIVE, 
                               colors=palette_size)
        # Find the color that occurs most often
        palette = paletted.getpalette()
        color_counts = sorted(paletted.getcolors(), reverse=True)

        colors = np.reshape(palette, (-1, 3))[:palette_size]
        colors = list(map(tuple, colors))
        # color_counts is a list of tuples: (count, index of color)
        # reorder colors to match the sorted counts
        colors = [colors[count[1]] for count in color_counts]

        return colors
        

    async def refresh_music_data(self, player, width, height):
        metadata = None
        try:
            metadata = await player.get_metadata()
        except DBusError as e:
            self.album_art = Image.open("../img/microphone-off.jpeg")
            self.title = "Service unavailable"
            # print(e.text)
            return
            
        if not metadata:
            return
        
        if self.switch_to_music:
            self.view = View.MUSIC
            
        self.music_last_updated = time.time()
        
        if "xesam:artist" in metadata:
            self.artist = metadata["xesam:artist"].value
        if "xesam:title" in metadata:
            self.title = metadata["xesam:title"].value
        if "xesam:album" in metadata:
            self.album = metadata["xesam:album"].value
        if "mpris:artUrl" in metadata:
            art_str = metadata["mpris:artUrl"].value
            art_str = art_str.replace("data:image/jpeg;base64,", "")
            art_base64 = BytesIO(b64decode(art_str))
            art_image = Image.open(art_base64)
            art_image.thumbnail((width, height), Image.Resampling.LANCZOS)
            
            diff = ImageChops.difference(art_image, self.album_art)
            art_changed = diff.getbbox() is not None

            self.album_art = art_image
            
            if art_changed or self.album_art_colors is None:
                self.album_art_colors = self.get_dominant_colors(art_image)
                print(self.album_art_colors)
                

def get_logo_x(homeaway: str) -> int:
    if homeaway == "home":
        return PANEL_WIDTH*2-LOGO_SIZE
    else:
        return 0


def get_score_x(homeaway: str, score: int, char_width: int = 10) -> int:
    score_space = PANEL_WIDTH - LOGO_SIZE
    score_width = len(score) * char_width
    if homeaway == "home":
        return int(PANEL_WIDTH + score_space/2 - score_width/2)
    else:
        return int(LOGO_SIZE + score_space/2 - score_width/2)


def get_shots_x(homeaway: str, shots: str, char_width: int = 5) -> int:
    if homeaway == "home":
        shots_width = len(shots) * char_width
        return int(PANEL_WIDTH*2-LOGO_SIZE-char_width-shots_width)
    else:
        return int(LOGO_SIZE + char_width)


async def matrix_loop(bus: MessageBus, matrix: RGBMatrix, data: Data,
                      eq_stream: EQStream):
    canvas = matrix.CreateFrameCanvas()

    font_4x6 = Font()
    font_4x6.LoadFont("../fonts/4x6.bdf")

    font_5x8 = Font()
    font_5x8.LoadFont("../fonts/5x8.bdf")
    
    font_8x13 = Font()
    font_8x13.LoadFont("../fonts/8x13.bdf")
    
    font_10x20 = Font()
    font_10x20.LoadFont("../fonts/10x20.bdf")
    
    white_text = Color(255, 255, 255)

    margin = 2
    linespace = 1

    offset = font_8x13.height + margin
    x = PANEL_WIDTH + margin
    y = offset
    
    title_y = y
    artist_y = y + font_8x13.height + linespace
    
    title_scroll = ScrollingText(font_8x13, white_text, x, title_y, 
                                 PANEL_WIDTH, PANEL_WIDTH*2, num_spaces=3,
                                 pause_dur=2.0)
    
    artist_scroll = ScrollingText(font_8x13, white_text, x, artist_y,
                                  PANEL_WIDTH, PANEL_WIDTH*2, num_spaces=3,
                                  pause_dur=2.0)
    
    play_scroll = ScrollingText(font_8x13, white_text, 0, PANEL_HEIGHT-2,
                                0, PANEL_WIDTH*2,
                                num_spaces=3, scroll_speed=2)
    
    while bus.connected:
        canvas.Clear()
        view = data.view

        # music_timeout = 5
        # last_updated = data.music_last_updated
        # if (last_updated is not None 
        #         and time.time() - last_updated  < music_timeout):
        if view is View.MUSIC:
            title = data.title
            artist = data.artist
            if title is not None:
                title_scroll.draw(canvas, title)
                
            if artist is not None:
                artists = ", ".join(artist)
                artist_scroll.draw(canvas, artists)
                
            if data.album_art is not None:
                canvas.SetImage(data.album_art)

            if eq_stream.frame_buffer.any():
                bar_height = 32
                eq_stream.draw_eq(canvas, 
                                  x=PANEL_WIDTH, 
                                  y=PANEL_HEIGHT-bar_height,
                                  num_bars=NUM_BARS, 
                                  bar_width=int(PANEL_WIDTH/NUM_BARS),
                                  max_height=bar_height,
                                  colors=data.album_art_colors)
        elif view is View.SPORTS:
            league: League = None
            team: Team = None
            
            if data.selected_league_abbr in data.sports:
                league = data.sports[data.selected_league_abbr]
            
            if league is not None and data.selected_team_abbr in league.teams:
                team = league.team(data.selected_team_abbr)
                
            if team is not None:
                attr = team.attributes
                sport = attr.get("sport")
                team_homeaway = attr.get("team_homeaway") or "home"
                oppo_homeaway = attr.get("opponent_homeaway") or "away"

                clock = attr.get("clock")
                if clock:
                    char_width = 5
                    clock_width = len(clock) * char_width
                    x = int(PANEL_WIDTH - clock_width/2)
                    y = font_5x8.height
                    DrawText(canvas, font_5x8, x, y, white_text, clock)
                
                logo_size = (LOGO_SIZE, LOGO_SIZE)
                logo_y = font_5x8.height + 2
                team_img = team.get_logo(logo_size)
                if team_img:
                    team_img_x = get_logo_x(team_homeaway)
                    canvas.SetImage(team_img, team_img_x, logo_y)
                
                oppo_abbr = attr.get("opponent_abbr")
                if oppo_abbr:
                    oppo = data.sports[league.abbr].team(oppo_abbr)
                    oppo_img = oppo.get_logo(logo_size)
                    oppo_img_x = get_logo_x(oppo_homeaway)
                    canvas.SetImage(oppo_img, oppo_img_x, logo_y)
                else:
                    league_img = league.get_logo(logo_size)
                    league_img_x = get_logo_x("away")
                    canvas.SetImage(league_img, league_img_x, logo_y)
                
                team_score = attr.get("team_score")
                if team_score:
                    x = get_score_x(team_homeaway, team_score)
                    y = 25
                    DrawText(canvas, font_10x20, x, y, white_text, team_score)
                        
                oppo_score = attr.get("opponent_score")
                if oppo_score:
                    x = get_score_x(oppo_homeaway, oppo_score)
                    y = 25
                    DrawText(canvas, font_10x20, x, y, white_text, oppo_score)
                    
                if sport == "hockey":
                    team_shots = attr.get("team_shots_on_target")
                    oppo_shots = attr.get("opponent_shots_on_target")
                    
                    if team_shots and oppo_shots:
                        char_width = 5
                        shots = "shots"
                        shots_width = len(shots) * char_width
                        x = int(PANEL_WIDTH - shots_width/2)
                        y = 35
                        DrawText(canvas, font_5x8, x, y, white_text, shots)
                    
                    if team_shots:
                        x = get_shots_x(team_homeaway, team_shots)
                        y = 45
                        DrawText(canvas, font_5x8, x, y, white_text, team_shots)
                            
                    if oppo_shots:
                        x = get_shots_x(oppo_homeaway, oppo_shots)
                        y = 45
                        DrawText(canvas, font_5x8, x, y, white_text, oppo_shots)
                        
                if sport == "baseball":
                    on_first = attr.get("on_first") or False
                    on_second = attr.get("on_second") or False
                    on_third = attr.get("on_third") or False
                    outs = attr.get("outs") or 0
                    balls = attr.get("balls") or 0
                    strikes = attr.get("strikes") or 0
                    
                    bases_bin = f"{int(on_third)}{int(on_second)}{int(on_first)}"
                    bases_img_file = f"../img/bases/bases_{bases_bin}.png"
                    bases_img = Image.open(bases_img_file)
                    bases_img = bases_img.convert("RGB")
                    
                    if bases_img:
                        bases_x = LOGO_SIZE + 2
                        bases_y = 30
                        canvas.SetImage(bases_img, bases_x, bases_y)
                        
                    x = PANEL_WIDTH + 3
                    y = 36
                    count = f"{balls}-{strikes}"
                    DrawText(canvas, font_5x8, x, y, white_text, count)
                    
                    MAX_OUTS = 3
                    radius = 3
                    out_space = 2
                    x = PANEL_WIDTH + out_space
                    y = 36 + radius
                    for o in range(MAX_OUTS):
                        out_size = radius*2
                        out = Image.new("RGB", (out_size,out_size))
                        draw = ImageDraw.Draw(out)
                        fill = (0,0,0)
                        if outs >= o+1:
                            fill = (255,255,255)
                        draw.ellipse((0,0,out_size-1,out_size-1), fill=fill,
                                     outline=(255,255,255))
                        canvas.SetImage(out, x, y)
                        x += out.width + out_space
                    
                last_play = attr.get("last_play")
                if last_play:
                    char_width = 8
                    play_width = len(last_play) * char_width
                    play_x = PANEL_WIDTH - play_width / 2
                    play_scroll._starting_x = play_x
                    play_scroll.draw(canvas, last_play)
                    
        elif view is View.DASHBOARD:
            now = datetime.now()
            now_str = now.strftime("%I:%M %m/%d/%Y")
            
            char_width = 8
            x = PANEL_WIDTH - (len(now_str) * char_width)/2
            y = font_8x13.height - 2
            DrawText(canvas, font_8x13, x, y, white_text, now_str)
            
            if data.averages:
                tmpr_avgs = data.averages.get("temperature").copy()
                if data.temperature_f is not None:
                    tmpr_avgs.append(round(data.temperature_f, 1))
                    
                hum_avgs = data.averages.get("humidity").copy()
                if data.humidity is not None:
                    hum_avgs.append(round(data.humidity, 1))
                    
                voc_avgs = data.averages.get("voc").copy()
                if data.voc is not None:
                    voc_avgs.append(round(data.voc))
                    
                co2_avgs = data.averages.get("co2").copy()
                if data.co2 is not None:
                    co2_avgs.append(round(data.co2))
                
                graphs = [
                    LineGraph("Temp", tmpr_avgs, "°F", round=1, 
                              line_color=(191, 29, 0),
                              fill_color=(51, 8, 0)),
                    LineGraph("Hum", hum_avgs, "%", round=1, 
                              line_color=(0, 76, 191),
                              fill_color=(0, 20, 51)),
                    LineGraph("VOC", voc_avgs, 
                              line_color=(109, 191, 119),
                              fill_color=(29, 51, 32)),
                    LineGraph("CO2", co2_avgs, "ppm", 
                              line_color=(187, 191, 172),
                              fill_color=(50, 51, 46))
                ]
                
                graph_x = 0
                background = (0, 0, 0)
                graph: LineGraph
                for i, graph in enumerate(graphs):
                    graph.background = background
                    graph_y = PANEL_HEIGHT - graph.height * (len(graphs)-i)
                    graph.draw(canvas, font_4x6, graph_x, graph_y, white_text)
                    background = graph.fill_color
        else:
            data.view = View.DASHBOARD

        canvas = matrix.SwapOnVSync(canvas)
        await asyncio.sleep(0.05)


async def air_loop(bus: MessageBus, data: Data):
    sgp = SGP40(I2C)
    scd = SCD30(I2C)
    while bus.connected:
        # since the measurement interval is long (2+ seconds)
        # we check for new data before reading
        # the values, to ensure current readings.
        if scd.data_available:
            data.temperature = scd.temperature
            data.humidity = scd.relative_humidity
            data.co2 = scd.CO2

        if data.temperature is not None and data.humidity is not None:
            voc = asyncio.to_thread(sgp.measure_index,
                                    data.temperature, data.humidity)
            gas = asyncio.to_thread(sgp.measure_raw,
                                    data.temperature, data.humidity)
            data.voc = await voc
            data.raw_gas = await gas

        # The voc algorithm expects a 1Hz sampling rate
        await asyncio.sleep(1)


async def mqtt_loop(bus: MessageBus, data: Data):
    address = subprocess.Popen(["cat","/sys/class/net/eth0/address"],
                               stdout=subprocess.PIPE, text=True)
    address.wait()
    mac = address.stdout.read().strip()

    password = os.environ.get("MQTT_PASSWORD")

    mqtt_settings = Settings.MQTT(host="172.16.1.2",
                                  username="nowspinning",
                                  password=password)
    
    device_info = DeviceInfo(name="nowspinning",
                             identifiers=mac,
                             manufacturer="Raspberry Pi Foundation",
                             viewl="Raspberry Pi 3B+")
    
    mqtt = MQTTDevice(mqtt_settings, device_info)

    mqtt.add_shared_sensor(name="Temperature",
                           unique_id="nowspinning_temperature",
                           device_class="temperature",
                           unit_of_measurement="°F",
                           value_template="{{ value_json.temperature }}")
    
    mqtt.add_shared_sensor(name="Humidity",
                           unique_id="nowspinning_humidity",
                           device_class="humidity",
                           unit_of_measurement="%",
                           value_template="{{ value_json.humidity }}")
    
    mqtt.add_shared_sensor(name="CO2",
                           unique_id="nowspinning_co2",
                           device_class="carbon_dioxide",
                           unit_of_measurement="ppm",
                           value_template="{{ value_json.co2 }}")
    
    mqtt.add_shared_sensor(name="VOC",
                           unique_id="nowspinning_voc",
                           device_class="aqi",
                           value_template="{{ value_json.voc }}")
    
    mqtt.add_shared_sensor(name="Artist",
                           unique_id="nowspinning_artist",
                           value_template="{{ value_json.artist }}",
                           icon="mdi:account-music")
    
    mqtt.add_shared_sensor(name="Album",
                           unique_id="nowspinning_album",
                           value_template="{{ value_json.album }}",
                           icon="mdi:album")
    
    mqtt.add_shared_sensor(name="Title",
                           unique_id="nowspinning_title",
                           value_template="{{ value_json.title }}",
                           icon="mdi:music-circle")
    
    views = [view.name.capitalize() for view in View]
    mqtt.add_select(name="View",
                    callback=callbacks.update_view,
                    user_data=data,
                    unique_id="nowspinning_view",
                    options=views)

    team_opts = []
    if data.selected_league_abbr:
        league = data.sports[data.selected_league_abbr]
        team_opts = league.friendly_team_names
        
    mqtt.add_select(name="Team",
                    callback=callbacks.update_team,
                    user_data=data,
                    unique_id="nowspinning_team",
                    options=team_opts)

    league_opts = []
    if data.sports:
        league_opts = list(data.sports.keys())
    
    mqtt.add_select(name="League",
                    callback=callbacks.update_league,
                    user_data={"data": data, 
                               "team_select": mqtt.entities["Team"]},
                    unique_id="nowspinning_league",
                    options=league_opts)

    mqtt.add_switch(name="Switch to Music",
                    callback=callbacks.music_switch,
                    user_data=data,
                    unique_id="nowspinning_music_switch",
                    icon="mdi:music-box-multiple")

    sports_sub_info = EntityInfo(name="Sports Sub",
                                 unique_id="nowspinning_sports_sub",
                                 component="sensor", device=device_info)
    sports_sub_settings = Settings(mqtt=mqtt_settings, entity=sports_sub_info)
    sports_sub = Subscriber(sports_sub_settings, callbacks.teamtracker, data)
    
    sports_sub.mqtt_client.subscribe("teamtracker/all")
    sports_sub.mqtt_client.publish("teamtracker/start", "start")
    
    avg_sub_info = EntityInfo(name="Averages Sub",
                              unique_id="nowspinning_avg_sub",
                              component="sensor", device=device_info)
    avg_sub_settings = Settings(mqtt=mqtt_settings, entity=avg_sub_info)
    avg_sub = Subscriber(avg_sub_settings, callbacks.averages, data)
    
    avg_sub.mqtt_client.subscribe("sensor-averages/all")
    avg_sub.mqtt_client.publish("sensor-averages/start", "start")
    
    mqtt.shared_sensor_topic = "hmd/sensor/nowspinning/state"

    for entitiy in mqtt.entities.values():
        entitiy.write_config()
        
    while bus.connected:
        entity: Discoverable
        for name, entity in mqtt.entities.items():
            if name not in ["League", "Team"]:
                entity.set_availability(True)
        
        payload = {}
        payload["temperature"] = f"{data.temperature_f:.1f}"
        payload["humidity"] = f"{data.humidity:.1f}"
        payload["co2"] = f"{int(data.co2)}"
        payload["voc"] = f"{data.voc}"
        artists = ""
        if data.artist is not None:
            artists = f"{','.join(data.artist)}"
        payload["artist"] = artists
        payload["album"] = f"{data.album}"
        payload["title"] = f"{data.title}"
        
        first = list(mqtt.entities.values())[0]
        first.set_state(json.dumps(payload))
        
        view_select = mqtt.entities["View"]

        view_select.set_selection(data.view.name.capitalize())
        
        team_select = mqtt.entities["Team"]
        
        league_select = mqtt.entities["League"]
        league_opts = list(data.sports.keys())
        
        if set(league_opts) != set(league_select._entity.options):
            league_select.update_options(league_opts)
                                
        league_select.set_selection(data.selected_league_abbr)
        if data.selected_league_abbr:
            league = data.sports[data.selected_league_abbr]
        
            team_opts = league.friendly_team_names
            
            if set(team_opts) != set(team_select._entity.options):
                team_select.update_options(team_opts)
                
            team_name = None
            if data.selected_team_abbr:
                team = league.team(data.selected_team_abbr)
                team_name = team.friendly_name
            
            team_select.set_selection(team_name)
                
        has_league_opts =  bool(league_select._entity.options)
        has_team_opts = bool(team_select._entity.options)
        league_select.set_availability(has_league_opts)
        team_select.set_availability(has_team_opts)
        
        music_switch = mqtt.entities["Switch to Music"]
        if data.switch_to_music:
            music_switch.on()
        else:
            music_switch.off()

        await asyncio.sleep(1)


def init_matrix():
    options = RGBMatrixOptions()
    options.rows = PANEL_WIDTH
    options.cols = PANEL_HEIGHT
    options.chain_length = 2
    options.parallel = 1
    options.hardware_mapping = "adafruit-hat-pwm"
    options.gpio_slowdown = 2
    #options.pwm_lsb_nanoseconds = 50
    #options.brightness = 50
    #options.pwm_bits = 8
    # options.show_refresh_rate = True

    matrix = RGBMatrix(options=options)
    return matrix


async def init_mpris():
    # The matrix has to run as root
    # but the songrec mpris only updates on session
    # So manually set it here
    os.environ["DBUS_SESSION_BUS_ADDRESS"] = "unix:path=/run/user/1000/bus"
    bus = await MessageBus().connect()

    tree = ET.parse("mpris.xml")

    obj = bus.get_proxy_object("org.mpris.MediaPlayer2.SongRec",
                               "/org/mpris/MediaPlayer2",
                               tree.getroot())

    player = obj.get_interface("org.mpris.MediaPlayer2.Player")
    properties = obj.get_interface("org.freedesktop.DBus.Properties")

    return bus, player, properties


async def loops(data: Data, eq_stream: EQStream):
    bus, player, properties = await init_mpris()
    matrix = init_matrix()
    
    await data.refresh_music_data(player, PANEL_WIDTH, PANEL_HEIGHT)

    async def on_prop_change(interface_name, changed_properties,
                             invalidated_properties):
        if "Metadata" in changed_properties:
            await data.refresh_music_data(player, PANEL_WIDTH, PANEL_HEIGHT)
           

    properties.on_properties_changed(on_prop_change)

    await asyncio.gather(matrix_loop(bus, matrix, data, eq_stream),
                         air_loop(bus, data),
                         mqtt_loop(bus, data))
    
    # await bus.wait_for_disconnect()


def main():
    data = Data()
    eq_stream = EQStream()
    fan = PWMOutputDevice(FAN_PIN)
    fan.value = 0.7

    asyncio.run(loops(data, eq_stream))
    eq_stream.stop()

     
if __name__ == "__main__":
    main()