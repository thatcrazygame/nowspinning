import asyncio
import os
import re
import signal
import subprocess

from callbacks import _UserData
from dotenv import load_dotenv
from ha_mqtt_discoverable import Settings, DeviceInfo
from paho.mqtt.client import Client, MQTTMessage

from mqttdevice import MQTTDevice
from utils import get_mac_address

load_dotenv()

is_running = True

CMDS = {
    "Nowspinning-Service-Restart": "sudo systemctl restart nowspinning",
    "Nowspinning-Service-Stop": "sudo systemctl stop nowspinning",
    "Songrec-Service-Restart": "systemctl --user restart songrec",
    "Songrec-Service-Stop": "systemctl --user stop songrec",
    "Pi-Backup": "sudo /usr/local/bin/image-backup /media/backup/backup.img",
    "Pi-Restart": "sudo reboot",
    "Pi-Shutdown": "sudo shutdown -h now",
}


def queue_command(client: Client, user_data: _UserData, message: MQTTMessage):
    cmd_rgx = r"\/([^\/]+?)\/command"
    cmd_search = re.search(cmd_rgx, message.topic)
    if not cmd_search:
        return

    cmd = cmd_search.group(1)
    if not cmd or cmd not in CMDS:
        return

    user_data["data"].put_nowait(cmd)


async def cmd_loop(mqtt: MQTTDevice, commands: asyncio.Queue):
    backup = mqtt.entities["Backup Running"]

    global is_running
    while is_running:
        if not commands.empty():
            cmd = await commands.get()
            params = CMDS[cmd]

            print(f"{cmd}: {params}")
            if cmd == "Pi-Backup":
                backup.on()

            proc = await asyncio.create_subprocess_shell(
                params, stdout=subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await proc.communicate()

            commands.task_done()
            print(f"{cmd}: Done")
            if cmd == "Pi-Backup":
                backup.off()

            if stdout:
                print(f"Output: {stdout.decode()}")
            if stderr:
                print(f"Error: {stderr.decode()}")

        await asyncio.sleep(1)


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
        elif status_search:
            service_status["status"] = status_search.group(1).strip()
            service_status["since"] = status_search.group(2).strip()
            service_status["uptime"] = status_search.group(3).strip()

    return service_status


async def init_mqtt(commands: asyncio.Queue):
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

    mqtt = MQTTDevice(
        mqtt_settings=mqtt_settings, device_info=device_info, user_data=commands
    )

    mqtt.add_sensor(
        name="Nowspinning Service",
        unique_id="nowspinning_service",
        icon="mdi:cog",
        entity_category="diagnostic",
        manual_availability=False,
        expire_after=10,
    )

    mqtt.add_sensor(
        name="Songrec Service",
        unique_id="songrec_service",
        icon="mdi:cog",
        entity_category="diagnostic",
        manual_availability=False,
        expire_after=10,
    )

    mqtt.add_binary_sensor(
        name="Backup Running",
        unique_id="backup_running",
        icon="mdi:backup-restore",
        entity_category="diagnostic",
        manual_availability=True,
    )

    mqtt.add_button(
        name="Nowspinning Service Restart",
        unique_id="nowspinning_service_restart",
        payload_press="NOWSPINNING",
        callback=queue_command,
        icon="mdi:cog-refresh",
        entity_category="diagnostic",
        manual_availability=False,
        expire_after=10,
    )

    mqtt.add_button(
        name="Songrec Service Restart",
        unique_id="songrec_service_restart",
        payload_press="SONGREC",
        callback=queue_command,
        icon="mdi:cog-refresh",
        entity_category="diagnostic",
        manual_availability=False,
        expire_after=10,
    )

    mqtt.add_button(
        name="Nowspinning Service Stop",
        unique_id="nowspinning_service_stop",
        payload_press="NOWSPINNING",
        callback=queue_command,
        icon="mdi:cog-stop",
        entity_category="diagnostic",
        manual_availability=False,
        expire_after=10,
    )

    mqtt.add_button(
        name="Songrec Service Stop",
        unique_id="songrec_service_stop",
        payload_press="SONGREC",
        callback=queue_command,
        icon="mdi:cog-stop",
        entity_category="diagnostic",
        manual_availability=False,
        expire_after=10,
    )

    mqtt.add_button(
        name="Pi Shutdown",
        unique_id="nowspinning_pi_shutdown",
        payload_press="SHUTDOWN",
        callback=queue_command,
        icon="mdi:power",
        entity_category="diagnostic",
        manual_availability=False,
        expire_after=10,
    )

    mqtt.add_button(
        name="Pi Reboot",
        unique_id="nowspinning_pi_reboot",
        payload_press="REBOOT",
        callback=queue_command,
        icon="mdi:restart",
        entity_category="diagnostic",
        manual_availability=False,
        expire_after=10,
    )

    mqtt.add_button(
        name="Pi Backup",
        unique_id="nowspinning_pi_backup",
        payload_press="BACKUP",
        callback=queue_command,
        icon="mdi:backup-restore",
        entity_category="diagnostic",
        manual_availability=False,
        expire_after=10,
    )

    await mqtt.connect_client()

    return mqtt


async def mqtt_loop(mqtt: MQTTDevice):
    nowspinning = mqtt.entities["Nowspinning Service"]
    songrec = mqtt.entities["Songrec Service"]
    backup = mqtt.entities["Backup Running"]

    backup.set_availability(True)
    backup.off()

    global is_running
    while is_running:
        ns = read_status("nowspinning")
        sr = read_status("songrec", is_user=True)

        update_sensor(ns, nowspinning)
        update_sensor(sr, songrec)

        await asyncio.sleep(5)

    backup.set_availability(False)


def update_sensor(systemctl, sensor):
    if systemctl and "status" in systemctl:
        sensor.set_state(systemctl["status"])
        del systemctl["status"]
        sensor.set_attributes(systemctl)


def stop(signum, frame):
    global is_running
    is_running = False


async def loops(commands: asyncio.Queue):
    mqtt = await init_mqtt(commands)
    await asyncio.gather(mqtt_loop(mqtt), cmd_loop(mqtt, commands))


def main():
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    commands = asyncio.Queue()
    asyncio.run(loops(commands))


if __name__ == "__main__":
    main()
