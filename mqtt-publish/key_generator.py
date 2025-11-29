import os
import time
import configparser

config = configparser.ConfigParser()
config.read("configuration.conf")
BASE_PATH = config.get("DATASET", "dir")
SENSOR_INTERVALS = {k: config.getint("SENSOR_INTERVALS", k) for k in config["SENSOR_INTERVALS"]}
SENSOR_TYPES = list(SENSOR_INTERVALS.keys())
DEFAULT_SENSOR_ID = config.getint("DATASET", "sensor_id")
BUILDING_ID = config.get("BUILDING", "id")


def generate_sensor_keys():
    """Il metodo serve per generar tutte le key dei sensori e i percorsi dei CSV"""
    sensor_keys = []
    for floor in os.listdir(BASE_PATH):
        floor_path = os.path.join(BASE_PATH, floor)
        if not os.path.isdir(floor_path):
            continue
        for room in os.listdir(floor_path):
            room_path = os.path.join(floor_path, room)
            if not os.path.isdir(room_path):
                continue
            for sensor_type in SENSOR_TYPES:
                files = [f for f in os.listdir(room_path) if f.startswith(sensor_type)]
                for idx, f in enumerate(files, start=DEFAULT_SENSOR_ID):
                    #idx mi serve per incrementare l'id del sensore nel caso ci fossero 
                    #piu sensori dello stesso tipo nella stessa stanza(nel dataset ciò non accade)
                    key = f"{BUILDING_ID}_{floor}_{room}_{sensor_type}_{idx}"
                    sensor_keys.append({
                        "key": key,
                        "floor": floor,
                        "room": room,
                        "sensor_type": sensor_type,
                        "file": os.path.join(room_path, f),
                        "interval": SENSOR_INTERVALS[sensor_type]
                    })
    return sensor_keys
