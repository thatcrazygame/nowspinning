import logging
import logging.config
import os
from shutil import chown
import subprocess
import yaml


class FilterMQTTPayload(logging.Filter):
    def __init__(self, level):
        self.level = level

    def filter(self, record):
        if "MQTT Message:" in record.msg and record.levelname == "INFO":
            return False
        else:
            return True


class LevelFilter(logging.Filter):
    def __init__(self, level):
        self.level = level

    def filter(self, record):
        if record.levelname == self.level:
            return True


def owned_file_handler(
    filename,
    mode="a",
    maxBytes=0,
    backupCount=0,
    encoding=None,
    owner=None,
    *args,
    **kwargs,
):
    if owner:
        if not os.path.exists(filename):
            open(filename, mode).close()
        chown(filename, *owner)
    print(filename, mode, encoding)
    return logging.handlers.RotatingFileHandler(
        filename, mode, maxBytes, backupCount, encoding
    )


def init_logging(log_config_file: str):
    with open(log_config_file, "r") as f:
        config = yaml.safe_load(f.read())
        logging.config.dictConfig(config)


def get_mac_address(net_type):
    address = subprocess.Popen(
        ["cat", f"/sys/class/net/{net_type}/address"], stdout=subprocess.PIPE, text=True
    )
    address.wait()
    mac = address.stdout.read().strip()
    return mac
