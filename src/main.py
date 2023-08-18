import asyncio
from gpiozero import PWMOutputDevice
import os
import signal
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET

from adafruit_sgp40 import SGP40
from adafruit_scd30 import SCD30
from board import SCL, SDA
from busio import I2C
from dbus_next.aio import MessageBus, ProxyInterface
from dotenv import load_dotenv
from ha_mqtt_discoverable import Settings, DeviceInfo
from rgbmatrix import RGBMatrix, RGBMatrixOptions

import callbacks
from constants import FORECAST_TYPE, PANEL_WIDTH, PANEL_HEIGHT, View
from data import Data
from mqttdevice import MQTTDevice, Discoverable
from sports import League, Team
from viewdraw import ViewDrawer
from viewdraw.dashboard import Dashboard
from viewdraw.musicinfo import MusicInfo
from viewdraw.off import Off
from viewdraw.scoreboard import Scoreboard
from viewdraw.gameoflife import GameOfLife
from viewdraw.weather import Weather

sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/.."))

# SCD-30 has tempremental I2C with clock stretching, datasheet recommends
# starting at 50KHz
I2C = I2C(SCL, SDA, frequency=50000)
FAN_PIN = 25
METERS_ABOVE_SEA_LEVEL = 274
TEMPERATURE_OFFSET = 6.0

load_dotenv()


async def matrix_loop(matrix: RGBMatrix, data: Data):
    canvas = matrix.CreateFrameCanvas()

    data.view_drawers[View.OFF] = Off()
    data.view_drawers[View.MUSIC] = MusicInfo()
    data.view_drawers[View.SCOREBOARD] = Scoreboard()
    data.view_drawers[View.DASHBOARD] = Dashboard()
    data.view_drawers[View.GAME_OF_LIFE] = GameOfLife()
    data.view_drawers[View.WEATHER] = Weather()
    while data.is_running:
        canvas.Clear()
        data.check_songrec_timeout()

        if data.view not in data.view_drawers:
            data.view = View.DASHBOARD

        view: ViewDrawer = data.view_drawers[data.view]
        await view.draw(canvas, data)

        canvas = matrix.SwapOnVSync(canvas)
        await asyncio.sleep(0.05)


async def air_loop(data: Data):
    sgp = SGP40(I2C)
    scd = SCD30(I2C)
    scd.temperature_offset = TEMPERATURE_OFFSET
    scd.altitude = METERS_ABOVE_SEA_LEVEL
    while data.is_running:
        # since the measurement interval is long (2+ seconds)
        # we check for new data before reading
        # the values, to ensure current readings.
        try:
            if scd.data_available:
                data.temperature = scd.temperature
                data.humidity = scd.relative_humidity
                data.co2 = scd.CO2

            if data.temperature is not None and data.humidity is not None:
                voc = asyncio.to_thread(
                    sgp.measure_index, data.temperature, data.humidity
                )
                gas = asyncio.to_thread(
                    sgp.measure_raw, data.temperature, data.humidity
                )
                data.voc = await voc
                data.raw_gas = await gas
        except Exception as e:
            print(f"ERROR: {e}")
            traceback.print_exc()

        # The voc algorithm expects a 1Hz sampling rate
        await asyncio.sleep(1)


async def mqtt_loop(data: Data):
    address = subprocess.Popen(
        ["cat", "/sys/class/net/eth0/address"], stdout=subprocess.PIPE, text=True
    )
    address.wait()
    mac = address.stdout.read().strip()

    password = os.environ.get("MQTT_PASSWORD")

    mqtt_settings = Settings.MQTT(
        host="172.16.1.2", username="nowspinning", password=password
    )

    device_info = DeviceInfo(
        name="nowspinning",
        identifiers=mac,
        manufacturer="Raspberry Pi Foundation",
        viewl="Raspberry Pi 3B+",
    )

    mqtt = MQTTDevice(
        mqtt_settings=mqtt_settings,
        device_info=device_info,
        user_data=data,
    )

    mqtt.add_sensor(
        name="Temperature",
        unique_id="nowspinning_temperature",
        device_class="temperature",
        unit_of_measurement="°F",
        value_template="{{ value_json.temperature.value }}",
        availability_template="{{ value_json.temperature.available }}",
        use_shared_topic=True,
    )

    mqtt.add_sensor(
        name="Humidity",
        unique_id="nowspinning_humidity",
        device_class="humidity",
        unit_of_measurement="%",
        value_template="{{ value_json.humidity.value }}",
        availability_template="{{ value_json.humidity.available }}",
        use_shared_topic=True,
    )

    mqtt.add_sensor(
        name="CO2",
        unique_id="nowspinning_co2",
        device_class="carbon_dioxide",
        unit_of_measurement="ppm",
        value_template="{{ value_json.co2.value }}",
        availability_template="{{ value_json.co2.available }}",
        use_shared_topic=True,
    )

    mqtt.add_sensor(
        name="VOC",
        unique_id="nowspinning_voc",
        device_class="aqi",
        # needs units to display as graph in HA
        unit_of_measurement="",
        value_template="{{ value_json.voc.value }}",
        availability_template="{{ value_json.voc.available }}",
        use_shared_topic=True,
    )

    mqtt.add_sensor(
        name="Artist",
        unique_id="nowspinning_artist",
        value_template="{{ value_json.artist.value }}",
        availability_template="{{ value_json.artist.available }}",
        icon="mdi:account-music",
        use_shared_topic=True,
    )

    mqtt.add_sensor(
        name="Album",
        unique_id="nowspinning_album",
        value_template="{{ value_json.album.value }}",
        availability_template="{{ value_json.album.available }}",
        icon="mdi:album",
        use_shared_topic=True,
    )

    mqtt.add_sensor(
        name="Title",
        unique_id="nowspinning_title",
        value_template="{{ value_json.title.value }}",
        availability_template="{{ value_json.title.available }}",
        icon="mdi:music-circle",
        use_shared_topic=True,
    )

    views = [view.value for view in View]
    mqtt.add_select(
        name="View",
        callback=callbacks.update_view,
        unique_id="nowspinning_view",
        options=views,
        value_template="{{ value_json.view.value }}",
        availability_template="{{ value_json.view.available }}",
        use_shared_topic=True,
    )

    team_opts = []
    if data.selected_league_abbr:
        league = data.sports[data.selected_league_abbr]
        team_opts = league.friendly_team_names

    mqtt.add_select(
        name="Team",
        callback=callbacks.update_team,
        unique_id="nowspinning_team",
        options=team_opts,
        value_template="{{ value_json.team.value }}",
        availability_template="{{ value_json.team.available }}",
        use_shared_topic=True,
    )

    league_opts = []
    if data.sports:
        league_opts = list(data.sports.keys())

    mqtt.add_select(
        name="League",
        callback=callbacks.update_league,
        unique_id="nowspinning_league",
        options=league_opts,
        value_template="{{ value_json.league.value }}",
        availability_template="{{ value_json.league.available }}",
        use_shared_topic=True,
    )

    mqtt.add_switch(
        name="Switch to Music",
        callback=callbacks.music_switch,
        unique_id="nowspinning_music_switch",
        icon="mdi:music-box-multiple",
        value_template="{{ value_json.music_switch.value }}",
        availability_template="{{ value_json.music_switch.available }}",
        use_shared_topic=True,
    )

    mqtt.add_subscriber_only(
        name="Sports Sub",
        unique_id="nowspinning_sports_sub",
        callback=callbacks.teamtracker,
        sub_topic="teamtracker/all",
        start_topic="teamtracker/start",
    )

    mqtt.add_subscriber_only(
        name="Averages Sub",
        unique_id="nowspinning_avg_sub",
        callback=callbacks.averages,
        sub_topic="sensor-averages/all",
        start_topic="sensor-averages/start",
    )

    mqtt.add_button(
        name="Game of Life Reset",
        unique_id="nowspinning_gol_reset",
        payload_press="RESET",
        callback=callbacks.game_of_life_buttons,
        icon="mdi:restart",
        availability_template="{{ value_json.gol_reset.available }}",
        use_shared_topic=True,
    )

    mqtt.add_button(
        name="Game of Life Add Noise",
        unique_id="nowspinning_gol_add_noise",
        payload_press="ADD_NOISE",
        callback=callbacks.game_of_life_buttons,
        icon="mdi:view-grid-plus",
        availability_template="{{ value_json.gol_add_noise.available }}",
        use_shared_topic=True,
    )

    mqtt.add_switch(
        name="Game of Life Show Gens",
        unique_id="nowspinning_gol_show_gens",
        callback=callbacks.game_of_life_gens_switch,
        icon="mdi:counter",
        value_template="{{ value_json.gol_show_gens.value }}",
        availability_template="{{ value_json.gol_show_gens.available }}",
        use_shared_topic=True,
    )

    mqtt.add_subscriber_only(
        name="Nowspinning Weather Forecast",
        unique_id="nowspinning_weather_forecast",
        callback=callbacks.weather,
        sub_topic="weather-forecast/all",
        start_topic="weather-forecast/start",
    )

    mqtt.add_select(
        name="Forecast Type",
        callback=callbacks.update_forecast_type,
        unique_id="nowspinning_forecast_type",
        options=list(FORECAST_TYPE),
        value_template="{{ value_json.forecast_type.value }}",
        availability_template="{{ value_json.forecast_type.available }}",
        use_shared_topic=True,
    )

    mqtt.connect_client()

    while data.is_running:
        team_select = mqtt.entities["Team"]
        league_select = mqtt.entities["League"]
        league_opts = list(data.sports.keys())
        league_select.update_options(league_opts)

        if data.selected_league_abbr is None and league_opts:
            data.selected_league_abbr = league_opts[0]

        if data.selected_league:
            league = data.selected_league
            team_opts = league.friendly_team_names
            team_select.update_options(team_opts)

        mqtt.set_shared_state(data.get_json())

        await asyncio.sleep(1)

    mqtt.set_all_availability(False)


def init_matrix():
    options = RGBMatrixOptions()
    options.rows = PANEL_WIDTH
    options.cols = PANEL_HEIGHT
    options.chain_length = 2
    options.parallel = 1
    options.hardware_mapping = "adafruit-hat-pwm"
    options.gpio_slowdown = 2
    # options.pwm_lsb_nanoseconds = 50
    # options.brightness = 50
    # options.pwm_bits = 8
    # options.show_refresh_rate = True

    matrix = RGBMatrix(options=options)
    return matrix


async def init_mpris() -> tuple[MessageBus, ProxyInterface, ProxyInterface]:
    # The matrix has to run as root
    # but the songrec mpris only updates on session
    # So manually set it here
    os.environ["DBUS_SESSION_BUS_ADDRESS"] = "unix:path=/run/user/1000/bus"
    bus = await MessageBus().connect()

    tree = ET.parse("mpris.xml")

    obj = bus.get_proxy_object(
        "org.mpris.MediaPlayer2.SongRec", "/org/mpris/MediaPlayer2", tree.getroot()
    )

    player = obj.get_interface("org.mpris.MediaPlayer2.Player")
    properties = obj.get_interface("org.freedesktop.DBus.Properties")

    return bus, player, properties


async def loops(data: Data):
    bus, player, properties = await init_mpris()
    matrix = init_matrix()

    await data.refresh_music_data(player, PANEL_WIDTH, PANEL_HEIGHT)

    async def on_prop_change(
        interface_name, changed_properties, invalidated_properties
    ):
        if "Metadata" in changed_properties:
            await data.refresh_music_data(player, PANEL_WIDTH, PANEL_HEIGHT)

    properties.on_properties_changed(on_prop_change)

    await asyncio.gather(matrix_loop(matrix, data), air_loop(data), mqtt_loop(data))

    bus.disconnect()


def main():
    data = Data()
    signal.signal(signal.SIGINT, data.stop)
    signal.signal(signal.SIGTERM, data.stop)

    fan = PWMOutputDevice(FAN_PIN)
    fan.value = 0.7

    asyncio.run(loops(data))


if __name__ == "__main__":
    main()
