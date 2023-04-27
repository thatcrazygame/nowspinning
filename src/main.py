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
from dotenv import load_dotenv
from ha_mqtt_discoverable import Settings, DeviceInfo, Discoverable, EntityInfo, Subscriber
from paho.mqtt.client import Client, MQTTMessage
from PIL import Image, ImageDraw, ImageFont
from rgbmatrix import RGBMatrix, RGBMatrixOptions
from rgbmatrix.graphics import Color, DrawText, Font

from scrollingtext import ScrollingText
from mqttdevice import MQTTDevice
from sports import League, Team
from customdiscoverable import Select, SharedSensor

sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/.."))

PANEL_WIDTH = 64
PANEL_HEIGHT = 64
# SCD-30 has tempremental I2C with clock stretching, datasheet recommends
# starting at 50KHz
I2C = I2C(SCL, SDA, frequency=50000)
FAN_PIN = 25

LOGO_SIZE = 40

load_dotenv()

class View(Enum):
    DASHBOARD = 1
    MUSIC = 2
    SPORTS = 3

class Data(object):
    """Class to share data between async functions"""

    def __init__(self):
        self.music_last_updated = None
        self.artist = None
        self.title = None
        self.album = None
        self.image = None
        self.temperature = None
        self.humidity = None
        self.co2 = None
        self.voc = None
        self.raw_gas = None
        self.view: View = View.DASHBOARD
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
        

    def refresh_music_data(self, metadata, width, height):
        if self.switch_to_music:
            self.view = View.MUSIC
            
        if metadata:
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
            self.image = art_image


async def matrix_loop(bus: MessageBus, matrix: RGBMatrix, data: Data):
    canvas = matrix.CreateFrameCanvas()

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
                                 PANEL_WIDTH, PANEL_WIDTH*2, num_spaces=3)
    
    artist_scroll = ScrollingText(font_8x13, white_text, x, artist_y,
                                  PANEL_WIDTH, PANEL_WIDTH*2, num_spaces=3)
    
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
            if title is not None and artist is not None:
                artists = ", ".join(artist)

                title_scroll.update_text(title)
                title_scroll.draw(canvas)
                
                artist_scroll.update_text(artists)
                artist_scroll.draw(canvas)
            
            if data.image is not None:
                canvas.SetImage(data.image)
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

                clock = attr.get("clock")
                if clock:
                    char_width = 5
                    clock_width = len(clock) * char_width
                    x = int(PANEL_WIDTH - clock_width/2)
                    y = font_5x8.height
                    DrawText(canvas, font_5x8, x, y, white_text, clock)
                
                logo_size = (LOGO_SIZE, LOGO_SIZE)
                
                team_img = team.get_logo(logo_size)
                if team_img:
                    canvas.SetImage(team_img, 0, font_5x8.height + 2)
                
                oppo_abbr = attr.get("opponent_abbr")
                if oppo_abbr:
                    oppo = data.sports[league.abbr].team(oppo_abbr)
                    oppo_img = oppo.get_logo(logo_size)
                    oppo_img_x = PANEL_WIDTH*2-LOGO_SIZE
                    canvas.SetImage(oppo_img, oppo_img_x, font_5x8.height + 2)
                else:
                    league_img = league.get_logo(logo_size)
                    canvas.SetImage(league_img, PANEL_WIDTH*2-league_img.width)    
                
                score_space = PANEL_WIDTH - LOGO_SIZE
                team_score = attr.get("team_score")
                if team_score:
                    char_width = 10
                    score_width = len(team_score) * char_width
                    x = int(LOGO_SIZE + score_space/2 - score_width/2)
                    y = 25
                    DrawText(canvas, font_10x20, x, y, white_text, team_score)
                        
                oppo_score = attr.get("opponent_score")
                if oppo_score:
                    char_width = 10
                    score_width = len(oppo_score) * char_width
                    x = int(PANEL_WIDTH + score_space/2 - score_width/2)
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
                        shots_width = len(team_shots) * char_width
                        x = int(LOGO_SIZE + char_width)
                        y = 45
                        DrawText(canvas, font_5x8, x, y, white_text, team_shots)
                            
                    if oppo_shots:
                        shots_width = len(oppo_shots) * char_width
                        x = int(PANEL_WIDTH*2-LOGO_SIZE-char_width-shots_width)
                        y = 45
                        DrawText(canvas, font_5x8, x, y, white_text, oppo_shots)
                        
                last_play = attr.get("last_play")
                if last_play:
                    char_width = 8
                    play_width = len(last_play) * char_width
                    play_x = PANEL_WIDTH - play_width / 2
                    play_scroll._starting_x = play_x
                    play_scroll.update_text(last_play)
                    play_scroll.draw(canvas)
                    
        elif view is View.DASHBOARD:
            now = datetime.now()
            x = margin
            y = font_8x13.height + margin
            DrawText(canvas, font_8x13, 0, y, white_text,
                     now.strftime("%I:%M"))
            
            y = y + font_8x13.height + margin
            DrawText(canvas, font_5x8, x, y, white_text,
                     now.strftime("%m/%d/%Y"))
            
            y = font_8x13.height + margin
            if data.temperature_f is not None:
                x = (matrix.width / 2) + margin
                DrawText(canvas, font_8x13, x, y, white_text,
                         f"{data.temperature_f:.1f}°F")
            
            if data.humidity is not None:
                y = y + font_5x8.height + margin
                DrawText(canvas, font_5x8, x, y, white_text,
                         f"Hum: {data.humidity:.1f}%")
            
            if data.co2 is not None:
                y = y + font_5x8.height + margin
                DrawText(canvas, font_5x8, x, y, white_text,
                         f"CO2: {int(data.co2)}ppm")
            
            if data.voc is not None:
                y = y + font_5x8.height + margin
                DrawText(canvas, font_5x8, x, y, white_text, 
                         f"VOC: {data.voc}")
        else:
            data.view = View.DASHBOARD

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

async def mqtt_loop(bus: MessageBus, matrix: RGBMatrix, data: Data):
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
                           value_template="{{ value_json.co2}}")
    
    mqtt.add_shared_sensor(name="VOC",
                           unique_id="nowspinning_voc",
                           device_class="aqi",
                           value_template="{{ value_json.voc}}")
    
    mqtt.add_shared_sensor(name="Artist",
                           unique_id="nowspinning_artist",
                           value_template="{{ value_json.artist}}",
                           icon="mdi:account-music")
    
    mqtt.add_shared_sensor(name="Album",
                           unique_id="nowspinning_album",
                           value_template="{{ value_json.album}}",
                           icon="mdi:album")
    
    mqtt.add_shared_sensor(name="Title",
                           unique_id="nowspinning_title",
                           value_template="{{ value_json.title }}",
                           icon="mdi:music-circle")
    
    def update_view(client: Client, user_data, message: MQTTMessage):
        view = str(message.payload.decode("UTF-8")).upper()
        data.view = View[view]
    
    views = [view.name.capitalize() for view in View]
    mqtt.add_select(name="View",
                    callback=update_view,
                    unique_id="nowspinning_view",
                    options=views)

    
    def update_team(client: Client, user_data, message: MQTTMessage):
        selected_name = str(message.payload.decode("UTF-8"))
        if selected_name and data.selected_league_abbr:
            league = data.sports[data.selected_league_abbr]
            for team in league.teams.values():
                team_name = team.friendly_name
                if team_name and team_name == selected_name:
                    data.selected_team_abbr = team.abbr
                    break
            
    team_opts = []
    if data.selected_league_abbr:
        league = data.sports[data.selected_league_abbr]
        team_opts = league.friendly_team_names
        
    mqtt.add_select(name="Team",
                    callback=update_team,
                    unique_id="nowspinning_team",
                    options=team_opts)


    def update_league(client: Client, user_data, message: MQTTMessage):
        league_abbr = str(message.payload.decode("UTF-8"))
        
        diff_league = data.selected_league_abbr != league_abbr
        if league_abbr in data.sports and diff_league:
            data.selected_league_abbr = league_abbr
            league = data.sports[league_abbr]
            if league.teams:
                first_team = list(league.teams.values())[0]
                data.selected_team_abbr = first_team.abbr
                team_select = mqtt.entities["Team"]
                team_names = league.friendly_team_names
                team_select.update_options(team_names)
                team_select.set_selection(None) # Maybe helps reset?
    
    
    league_opts = []
    if data.sports:
        league_opts = list(data.sports.keys())
    
    mqtt.add_select(name="League",
                    callback=update_league,
                    unique_id="nowspinning_league",
                    options=league_opts)
    
    def music_switch(client: Client, user_data, message: MQTTMessage):
        state = str(message.payload.decode("UTF-8"))
        data.switch_to_music = (state == "ON")

    
    mqtt.add_switch(name="Switch to Music",
                    callback=music_switch,
                    unique_id="nowspinning_music_switch",
                    icon="mdi:music-box-multiple")

    def teamtracker(client: Client, user_data, message: MQTTMessage):
        payload = json.loads(str(message.payload.decode("UTF-8")))
        if "teams" not in payload: return
        
        for team in payload["teams"]:
            league_abbr = team["league"]
            team_abbr = team["team_abbr"]

            if league_abbr not in data.sports:
                data.sports[league_abbr] = League(league_abbr)
            
            state: str = team["state"]
            new_attr: dict = team["attributes"]
            
            for attr in new_attr:
                if type(new_attr[attr]) is list:
                    new_attr[attr] = tuple(new_attr[attr])
              
            team = data.sports[league_abbr].team(team_abbr)
            prev_attr = team.attributes
        
            diff = dict(set(new_attr.items()) - set(prev_attr.items()))
        
            data.sports[league_abbr].team(team_abbr, attributes=new_attr,
                                          changes=diff, game_state=state)


    et = EntityInfo(name="Sports Sub", unique_id="nowspinning_sports_sub",
                    component="sensor", device=device_info)
    settings = Settings(mqtt=mqtt_settings, entity=et)
    sub = Subscriber(settings, teamtracker, None)
    
    sub.mqtt_client.subscribe("teamtracker/all")
    sub.mqtt_client.publish("teamtracker/start", "start")
    
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


async def main():
    bus, player, properties = await init_mpris()
    matrix = init_matrix()

    data = Data()
    metadata = await player.get_metadata()
    data.refresh_music_data(metadata, PANEL_WIDTH, PANEL_HEIGHT)

    async def on_prop_change(interface_name, changed_properties,
                             invalidated_properties):
        if "Metadata" in changed_properties:
            metadata = await player.get_metadata()
            data.refresh_music_data(metadata, PANEL_WIDTH, PANEL_HEIGHT)
           

    properties.on_properties_changed(on_prop_change)

    await asyncio.gather(matrix_loop(bus, matrix, data),
                         air_loop(bus, matrix, data),
                         mqtt_loop(bus, matrix, data))
    
    await bus.wait_for_disconnect()

if __name__ == "__main__":
    fan = PWMOutputDevice(FAN_PIN)
    fan.value = 0.7
    asyncio.run(main())