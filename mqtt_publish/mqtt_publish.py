import os
import time
import csv
import json
import configparser
import paho.mqtt.client as mqtt
"""Lo scopo di mqtt_publish è quello di simulare i dati provenienti da dei sensori IoT sfruttando il protocollo
MQTT avendo come broker Mosquitto"""

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
CONF_PATH = os.path.join(PROJECT_ROOT, "configuration.conf")
config = configparser.ConfigParser()
config.read(CONF_PATH)
MQTT_BROKER = config.get("MQTT", "broker")
MQTT_PORT = config.getint("MQTT", "port")
TOPIC_PREFIX = config.get("MQTT", "topic_prefix")
MQTT_QOS = 1
BUILDING_ID = config.get("BUILDING", "id")
DATA_DIR_RELATIVE= config.get("DATASET", "dir")
BASE_PATH = os.path.abspath(os.path.join(PROJECT_ROOT, DATA_DIR_RELATIVE))
DEFAULT_SENSOR_ID = config.getint("DATASET", "sensor_id")
SENSOR_INTERVALS = {k: config.getint("SENSOR_INTERVALS", k) for k in config["SENSOR_INTERVALS"]}
SENSOR_TYPES = list(SENSOR_INTERVALS.keys())

client = mqtt.Client()
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()  

def generate_sensor_keys():
    """Il metodo serve per generare tutte le key dei sensori e i percorsi dei CSV per simulare il flusso di dati
    generabili da una vera topologia di dispositivi IoT sfruttando il dataset già presente."""
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
                    #piu sensori dello stesso tipo nella stessa stanza
                    # (nel nostro caso nel dataset ciò non accade  in quanto c'è un solo tipo di sensore per stanza)
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

def publish_sensor_data(sensor_info):
    """Legge il CSV e pubblica i messaggi MQTT simulando tempi reali ovvero 10 secondi 
    per il pir e 5 secondi per gli altri sensori presenti nelle stanze."""
    with open(sensor_info["file"], newline='') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if len(row) < 2:
                continue
            timestamp, value = row[0], row[1]
            payload = {
                "timestamp": int(timestamp),
                "building": BUILDING_ID,
                "floor": sensor_info["floor"],
                "room": sensor_info["room"],
                "sensor_type": sensor_info["sensor_type"],
                "sensor_id": sensor_info["key"],
                "value": float(value)
            }
            topic = f"{TOPIC_PREFIX}{sensor_info['floor']}/{sensor_info['room']}/{sensor_info['sensor_type']}"
            client.publish(topic, json.dumps(payload), qos=MQTT_QOS)
            print(f"Published {sensor_info['key']} -> {payload}")
            #time.sleep(sensor_info["interval"])

def main():
    sensors = generate_sensor_keys()
    print(f"Trovati {len(sensors)} sensori, avvio pubblicazione messaggi...")
    while True:
        for sensor in sensors:
            publish_sensor_data(sensor)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Fine")
    finally:
        client.loop_stop()
        client.disconnect()
