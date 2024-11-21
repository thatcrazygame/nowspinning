import asyncio
import os
import re
import signal
import subprocess

from callbacks import _process_message, _UserData
from dotenv import load_dotenv
from ha_mqtt_discoverable import Settings, DeviceInfo
from paho.mqtt.client import Client, MQTTMessage

from mqttdevice import MQTTDevice
from utils import get_mac_address

load_dotenv()

is_running = True

SERVICES = {"NOWSPINNING": False, "SONGREC": True}
ACTIONS = ["restart", "stop"]


def service_ctl(service, action):
    if (service and service not in SERVICES) or action not in ACTIONS:
        return

    is_user = SERVICES[service]
    systemctl = "systemctl --user" if is_user else "sudo systemctl"
    os.system(f"{systemctl} {action} {service.lower()}")


def service_restart(client: Client, user_data: _UserData, message: MQTTMessage):
    payload = _process_message(message)
    service_ctl(payload, "restart")


def service_stop(client: Client, user_data: _UserData, message: MQTTMessage):
    payload = _process_message(message)
    service_ctl(payload, "stop")


def system_shutdown(client: Client, user_data: _UserData, message: MQTTMessage):
    payload = _process_message(message)
    if payload == "SHUTDOWN":
        os.system("sudo shutdown -h now")


def system_reboot(client: Client, user_data: _UserData, message: MQTTMessage):
    payload = _process_message(message)
    if payload == "REBOOT":
        os.system("sudo reboot")


def read_status(service, is_user=False):
    params = ["systemctl", "status", service]
    if is_user:
        params.insert(1, "--user")

    p = subprocess.Popen(params, stdout=subprocess.PIPE)
    (output, err) = p.communicate()
    output = output.decode("utf-8")

    service_regx = r"Loaded:.*\/(.*service);"
    status_regx = r"Active:(.*) since (.*);(.*)"
    service_status = {}
    for line in output.splitlines():
        service_search = re.search(service_regx, line)
        status_search = re.search(status_regx, line)

        if service_search:
            service_status["service"] = service_search.group(1)
            # print("service:", service)

        elif status_search:
            service_status["status"] = status_search.group(1).strip()
            # print("status:", status.strip())
            service_status["since"] = status_search.group(2).strip()
            # print("since:", since.strip())
            service_status["uptime"] = status_search.group(3).strip()
            # print("uptime:", uptime.strip())

    return service_status


async def mqtt_loop():
    mac = get_mac_address("eth0")

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

    mqtt = MQTTDevice(mqtt_settings=mqtt_settings, device_info=device_info)

    nowspinning = mqtt.add_sensor(
        name="Nowspinning Service",
        unique_id="nowspinning_service",
        icon="mdi:cog",
        entity_category="diagnostic",
        manual_availability=False,
        expire_after=10,
    )

    songrec = mqtt.add_sensor(
        name="Songrec Service",
        unique_id="songrec_service",
        icon="mdi:cog",
        entity_category="diagnostic",
        manual_availability=False,
        expire_after=10,
    )

    mqtt.add_button(
        name="Nowspinning Service Restart",
        unique_id="nowspinning_service_restart",
        payload_press="NOWSPINNING",
        callback=service_restart,
        icon="mdi:cog-refresh",
        entity_category="diagnostic",
        manual_availability=False,
        expire_after=10,
    )

    mqtt.add_button(
        name="Songrec Service Restart",
        unique_id="songrec_service_restart",
        payload_press="SONGREC",
        callback=service_restart,
        icon="mdi:cog-refresh",
        entity_category="diagnostic",
        manual_availability=False,
        expire_after=10,
    )

    mqtt.add_button(
        name="Nowspinning Service Stop",
        unique_id="nowspinning_service_stop",
        payload_press="NOWSPINNING",
        callback=service_stop,
        icon="mdi:cog-stop",
        entity_category="diagnostic",
        manual_availability=False,
        expire_after=10,
    )

    mqtt.add_button(
        name="Songrec Service Stop",
        unique_id="songrec_service_stop",
        payload_press="SONGREC",
        callback=service_stop,
        icon="mdi:cog-stop",
        entity_category="diagnostic",
        manual_availability=False,
        expire_after=10,
    )

    mqtt.add_button(
        name="Pi Shutdown",
        unique_id="nowspinning_pi_shutdown",
        payload_press="SHUTDOWN",
        callback=system_shutdown,
        icon="mdi:power",
        entity_category="diagnostic",
        manual_availability=False,
        expire_after=10,
    )

    mqtt.add_button(
        name="Pi Reboot",
        unique_id="nowspinning_pi_reboot",
        payload_press="REBOOT",
        callback=system_reboot,
        icon="mdi:restart",
        entity_category="diagnostic",
        manual_availability=False,
        expire_after=10,
    )

    await mqtt.connect_client()

    global is_running
    while is_running:
        ns = read_status("nowspinning")
        sr = read_status("songrec", is_user=True)

        nowspinning.set_state(ns["status"])
        del ns["status"]
        nowspinning.set_attributes(ns)

        songrec.set_state(sr["status"])
        del sr["status"]
        songrec.set_attributes(sr)

        await asyncio.sleep(5)


def stop(signum, frame):
    global is_running
    is_running = False


def main():
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    asyncio.run(mqtt_loop())


if __name__ == "__main__":
    main()
