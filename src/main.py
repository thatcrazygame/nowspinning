from utils import init_logging

init_logging("logging.yaml")

import asyncio
from gpiozero import PWMOutputDevice
import logging
import os
import signal
import sys
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
from constants import (
    DEFAULT_VIEW,
    FAN_PIN,
    METERS_ABOVE_SEA_LEVEL,
    TEMPERATURE_OFFSET,
    FORECAST_TYPE,
    SECONDARY_TYPE,
    PANEL_WIDTH,
    PANEL_HEIGHT,
)
from data import Data
from mqttdevice import MQTTDevice, Discoverable

from utils import get_mac_address
from view import View, VIEWS

sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/.."))

# SCD-30 has tempremental I2C with clock stretching
# datasheet recommends starting at 50KHz
# updated in /boot/config.txt
I2C = I2C(SCL, SDA)

logger = logging.getLogger(__name__)
load_dotenv()


async def matrix_loop(matrix: RGBMatrix, data: Data):
    logger.info("Init matrix loop")
    canvas = matrix.CreateFrameCanvas()

    view_names = [v for v in VIEWS.keys()]
    logger.info(f"Init views: {','.join(view_names)}")
    max_unexpected_errors = 5
    unexpected_errors = 0
    current_view: View = None
    while data.is_running:
        canvas.Clear()

        if data.view not in VIEWS:
            data.view = DEFAULT_VIEW

        data_view = VIEWS[data.view]
        if current_view is not data_view:
            if current_view is not None:
                current_view.unload()
            data_view.load()

        current_view = data_view
        try:
            await current_view.draw(canvas, data)
            unexpected_errors = 0  # reset if we got here
        except Exception as e:
            if unexpected_errors >= max_unexpected_errors:
                continue

            logger.critical(f"Unexpected error drawing {data.view} view", exc_info=True)

            unexpected_errors += 1
            if unexpected_errors >= max_unexpected_errors:
                logger.critical(
                    f"Max errors ({max_unexpected_errors}) reached. The previous error will not be logged again until resolved or restarted."
                )

        canvas = matrix.SwapOnVSync(canvas)
        await asyncio.sleep(0)


async def air_loop(data: Data):
    logger.info("Init air sensors")
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
            logger.exception("Error getting air data")

        # The voc algorithm expects a 1Hz sampling rate
        await asyncio.sleep(1)


async def mqtt_loop(data: Data):
    # this should probably be wlan0 since it's connected to wifi, but not going to change it now
    mac = get_mac_address("eth0")

    logger.info("Init MQTT")

    password = os.environ.get("MQTT_PASSWORD")
    mqtt_settings = Settings.MQTT(
        host="172.16.1.3", username="nowspinning", password=password
    )

    device_info = DeviceInfo(
        name="nowspinning",
        identifiers=mac,
        manufacturer="Raspberry Pi Foundation",
        model="Raspberry Pi 4B",
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
        icon="mdi:air-filter",
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

    views = [view for view in sorted(VIEWS, key=lambda v: VIEWS[v].sort)]
    mqtt.add_select(
        name="View",
        callback=callbacks.update_view,
        unique_id="nowspinning_view",
        options=views,
        value_template="{{ value_json.view.value }}",
        availability_template="{{ value_json.view.available }}",
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

    mqtt.add_number(
        name="Music Timeout",
        callback=callbacks.music_timeout_number,
        unique_id="nowspinning_music_timeout",
        icon="mdi:timer-refresh",
        value_template="{{ value_json.music_timeout.value }}",
        availability_template="{{ value_json.music_timeout.available }}",
        use_shared_topic=True,
        mode="box",
        max=7200,
    )

    mqtt.add_button(
        name="Songrec Reset",
        unique_id="nowspinning_songrec_reset",
        payload_press="RESET",
        callback=callbacks.songrec_reset_button,
        icon="mdi:refresh",
        availability_template="{{ value_json.songrec_reset.available }}",
        use_shared_topic=True,
    )

    mqtt.add_subscriber_only(
        name="Game Sub",
        unique_id="nowspinning_game_sub",
        callback=callbacks.teamtracker,
        sub_topic="teamtracker/#",
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

    mqtt.add_sensor(
        name="Game of Life Generations",
        unique_id="nowspinning_gol_generations",
        # needs units to display as graph in HA
        unit_of_measurement="",
        icon="mdi:counter",
        value_template="{{ value_json.gol_generations.value }}",
        availability_template="{{ value_json.gol_generations.available }}",
        use_shared_topic=True,
    )

    mqtt.add_sensor(
        name="Game of Life Cells",
        unique_id="nowspinning_gol_cells",
        # needs units to display as graph in HA
        unit_of_measurement="",
        icon="mdi:dots-square",
        value_template="{{ value_json.gol_cells.value }}",
        availability_template="{{ value_json.gol_cells.available }}",
        use_shared_topic=True,
    )

    mqtt.add_number(
        name="Game of Life Seconds Per Tick",
        callback=callbacks.game_of_life_spt,
        unique_id="nowspinning_gol_seconds_per_tick",
        icon="mdi:play-speed",
        value_template="{{ value_json.gol_seconds_per_tick.value }}",
        availability_template="{{ value_json.gol_seconds_per_tick.available }}",
        use_shared_topic=True,
        mode="slider",
        min=0.0,
        max=10.0,
        step=0.1,
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
        options=FORECAST_TYPE,
        value_template="{{ value_json.forecast_type.value }}",
        availability_template="{{ value_json.forecast_type.available }}",
        use_shared_topic=True,
    )

    secondary_opts = list(SECONDARY_TYPE.keys())
    mqtt.add_select(
        name="Secondary Info",
        callback=callbacks.update_secondary_type,
        unique_id="nowspinning_secondary_info",
        options=secondary_opts,
        value_template="{{ value_json.secondary_type.value }}",
        availability_template="{{ value_json.secondary_type.available }}",
        use_shared_topic=True,
    )

    mqtt.add_subscriber_only(
        name="Flappy Bird Commands",
        unique_id="nowspinning_flappy_bird_commands",
        callback=callbacks.flappy_bird_commands,
        sub_topic="flappy-bird/commands",
        start_topic="flappy-bird/start",
    )

    await mqtt.connect_client()

    while data.is_running:
        await mqtt.set_shared_state(data.get_json())
        await asyncio.sleep(1)

    offline_payload = data.get_json().replace("online", "offline")
    await mqtt.set_shared_state(offline_payload)


def init_matrix():
    logger.info("Init matrix")
    options = RGBMatrixOptions()
    options.rows = PANEL_WIDTH
    options.cols = PANEL_HEIGHT
    options.chain_length = 2
    options.parallel = 1
    options.hardware_mapping = "adafruit-hat-pwm"
    options.gpio_slowdown = 4
    # options.pwm_lsb_nanoseconds = 50
    # options.brightness = 50
    # options.pwm_bits = 8
    # options.show_refresh_rate = True

    matrix = RGBMatrix(options=options)
    return matrix


async def init_mpris() -> tuple[MessageBus, ProxyInterface, ProxyInterface]:
    logger.info("Init mpris")
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

    # await data.refresh_music_data(player, PANEL_WIDTH, PANEL_HEIGHT)

    async def on_prop_change(
        interface_name, changed_properties, invalidated_properties
    ):
        if "Metadata" in changed_properties:
            await data.refresh_music_data(player, PANEL_WIDTH, PANEL_HEIGHT)

    properties.on_properties_changed(on_prop_change)

    await asyncio.gather(matrix_loop(matrix, data), air_loop(data), mqtt_loop(data))

    bus.disconnect()


def main():
    logger.info("Init Data")
    data = Data()
    signal.signal(signal.SIGINT, data.stop)
    signal.signal(signal.SIGTERM, data.stop)

    logger.info("Start fan")
    fan = PWMOutputDevice(FAN_PIN)
    fan.value = 0.7

    asyncio.run(loops(data))


if __name__ == "__main__":
    main()
