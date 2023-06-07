import asyncio
from gpiozero import PWMOutputDevice
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

from adafruit_sgp40 import SGP40
from adafruit_scd30 import SCD30
from board import SCL, SDA
from busio import I2C
from dbus_next.aio import MessageBus
from dotenv import load_dotenv
from ha_mqtt_discoverable import Settings, DeviceInfo, Discoverable
from rgbmatrix import RGBMatrix, RGBMatrixOptions

import callbacks
from constants import PANEL_WIDTH, PANEL_HEIGHT, View
from data import Data
from mqttdevice import MQTTDevice
from sports import League, Team
from viewdraw import ViewDrawer
from viewdraw.dashboarddrawer import DashboardDrawer
from viewdraw.musicdrawer import MusicDrawer
from viewdraw.offdrawer import OffDrawer
from viewdraw.sportsdrawer import SportsDrawer
from viewdraw.gameoflife import GameOfLife

sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/.."))

# SCD-30 has tempremental I2C with clock stretching, datasheet recommends
# starting at 50KHz
I2C = I2C(SCL, SDA, frequency=50000)
FAN_PIN = 25

load_dotenv()

async def matrix_loop(bus: MessageBus, matrix: RGBMatrix, data: Data):
    canvas = matrix.CreateFrameCanvas()

    views = {}
    views[View.OFF] = OffDrawer()
    views[View.MUSIC] = MusicDrawer()
    views[View.SPORTS] = SportsDrawer()
    views[View.DASHBOARD] = DashboardDrawer()
    views[View.GAME_OF_LIFE] = GameOfLife()
    while bus.connected:
        canvas.Clear()
        if data.view not in views:
            data.view = View.DASHBOARD
            
        view: ViewDrawer = views[data.view]
        await view.draw(canvas, data)

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
    
    views = [view.name.replace("_", " ").title() for view in View]
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
                    options=team_opts,
                    always_available=False)

    league_opts = []
    if data.sports:
        league_opts = list(data.sports.keys())
    
    mqtt.add_select(name="League",
                    callback=callbacks.update_league,
                    user_data={"data": data, 
                               "team_select": mqtt.entities["Team"]},
                    unique_id="nowspinning_league",
                    options=league_opts,
                    always_available=False)

    mqtt.add_switch(name="Switch to Music",
                    callback=callbacks.music_switch,
                    user_data=data,
                    unique_id="nowspinning_music_switch",
                    icon="mdi:music-box-multiple")

    mqtt.add_subscriber_only(name="Sports Sub",
                             unique_id="nowspinning_sports_sub",
                             callback=callbacks.teamtracker,
                             user_data=data,
                             sub_topic="teamtracker/all",
                             start_topic="teamtracker/start",
                             always_available=False)
    
    mqtt.add_subscriber_only(name="Averages Sub",
                             unique_id="nowspinning_avg_sub",
                             callback=callbacks.averages,
                             user_data=data,
                             sub_topic="sensor-averages/all",
                             start_topic="sensor-averages/start",
                             always_available=False)

    mqtt.shared_sensor_topic = "hmd/sensor/nowspinning/state"
    
    mqtt.add_button(name="Game of Life Reset",
                    unique_id="nowspinning_gol_reset",
                    payload_press="RESET",
                    callback=callbacks.game_of_life_buttons,
                    user_data=data,
                    icon="mdi:restart",
                    always_available=False)
    
    mqtt.add_button(name="Game of Life Add Noise",
                    unique_id="nowspinning_gol_add_noise",
                    payload_press="ADD_NOISE",
                    callback=callbacks.game_of_life_buttons,
                    user_data=data,
                    icon="mdi:view-grid-plus",
                    always_available=False)
    
    mqtt.add_switch(name="Game of Life Show Gens",
                    unique_id="nowspinning_gol_show_gens",
                    callback=callbacks.game_of_life_gens_switch,
                    user_data=data,
                    icon="mdi:counter",
                    always_available=False)

    for entitiy in mqtt.entities.values():
        entitiy.write_config()
        
    while bus.connected:
        is_gol_view = data.view is View.GAME_OF_LIFE
        entity: Discoverable
        for name, entity in mqtt.entities.items():
            is_gol_entity = "Game of Life" in name
            if entity.always_available:
                entity.set_availability(True)
            elif is_gol_entity:
                entity.set_availability(is_gol_view)
        
        first = list(mqtt.entities.values())[0]
        first.set_state(data.get_json())
        
        view_select = mqtt.entities["View"]

        view_select.set_selection(data.view.name.replace("_", " ").title())
        
        team_select = mqtt.entities["Team"]
        
        league_select = mqtt.entities["League"]
        league_opts = list(data.sports.keys())
        
        if set(league_opts) != set(league_select._entity.options):
            league_select.update_options(league_opts)
            
        if data.selected_league_abbr is None and league_opts:
            data.selected_league_abbr = league_opts[0]
                                
        league_select.set_selection(data.selected_league_abbr)
        if data.selected_league_abbr:
            league: League = data.sports[data.selected_league_abbr]
    
            team_opts = league.friendly_team_names
            if set(team_opts) != set(team_select._entity.options):
                team_select.update_options(team_opts)
                
            if data.selected_team_abbr:
                team = league.team(data.selected_team_abbr)
            else:
                teams = list(league.teams.values())
                teams.sort(key=Team.by_game_state, reverse=True)
                
                team = teams[0]
                data.selected_team_abbr = team.abbr
                
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
            
        gol_switch = mqtt.entities["Game of Life Show Gens"]
        if data.game_of_life_show_gens:
            gol_switch.on()
        else:
            gol_switch.off()

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


async def loops(data: Data):
    bus, player, properties = await init_mpris()
    matrix = init_matrix()
    
    await data.refresh_music_data(player, PANEL_WIDTH, PANEL_HEIGHT)

    async def on_prop_change(interface_name, changed_properties,
                             invalidated_properties):
        if "Metadata" in changed_properties:
            await data.refresh_music_data(player, PANEL_WIDTH, PANEL_HEIGHT)
           

    properties.on_properties_changed(on_prop_change)

    await asyncio.gather(matrix_loop(bus, matrix, data),
                         air_loop(bus, data),
                         mqtt_loop(bus, data))
    
    # await bus.wait_for_disconnect()


def main():
    data = Data()
    fan = PWMOutputDevice(FAN_PIN)
    fan.value = 0.7

    asyncio.run(loops(data))
    data.eq_stream.stop()

     
if __name__ == "__main__":
    main()