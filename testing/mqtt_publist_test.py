import os
import time
import csv
import json
import configparser
import paho.mqtt.client as mqtt

config = configparser.ConfigParser()
config.read("configuration.conf")

MQTT_BROKER = config.get("MQTT", "broker", fallback="localhost")
MQTT_PORT = config.getint("MQTT", "port", fallback=1883)
TOPIC_PREFIX = config.get("MQTT", "topic_prefix", fallback="/POLOA/")
BUILDING_ID = config.get("BUILDING", "id", fallback="POLOA")
BASE_PATH = config.get("DATASET", "dir", fallback="./data/raw_dataset")
SENSOR_INTERVALS = {k: config.getint("SENSOR_INTERVALS", k) for k in config["SENSOR_INTERVALS"]}

client = mqtt.Client()
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()

print(f"Connesso a MQTT broker {MQTT_BROKER}:{MQTT_PORT}")

def generate_sensor_metadata():
    sensors = []
    for floor in sorted(os.listdir(BASE_PATH)):
        floor_path = os.path.join(BASE_PATH, floor)
        if not os.path.isdir(floor_path):
            continue

        for room in sorted(os.listdir(floor_path)):
            room_path = os.path.join(floor_path, room)
            if not os.path.isdir(room_path):
                continue

            for sensor_file in os.listdir(room_path):
                if not sensor_file.endswith(".csv"):
                    continue

                sensor_type = sensor_file.replace(".csv", "")
                csv_path = os.path.join(room_path, sensor_file)

                sensors.append({
                    "building": BUILDING_ID,
                    "floor": floor,     
                    "room": room,       
                    "sensor_type": sensor_type,
                    "file": csv_path,
                    "interval": SENSOR_INTERVALS.get(sensor_type, 5)
                })
    return sensors


def publish_sensor_data(sensor):
    with open(sensor["file"], newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 2:
                continue
            timestamp, value = row[0], row[1]
            payload = {
                "timestamp": int(timestamp),
                "building": sensor["building"],
                "floor": sensor["floor"],
                "room": sensor["room"],
                "sensor_type": sensor["sensor_type"],
                "value": float(value)
            }
            topic = f"{TOPIC_PREFIX}{sensor['floor']}/{sensor['room']}/{sensor['sensor_type']}"
            client.publish(topic, json.dumps(payload))
            print(f"📡 Pubblicato su {topic}: {payload}")
            time.sleep(sensor["interval"])


def main():
    sensors = generate_sensor_metadata()
    print(f"Trovati {len(sensors)} sensori totali nel dataset")
    print("Inizio simulazione... (CTRL+C per interrompere)")

    while True:
        for sensor in sensors:
            publish_sensor_data(sensor)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n STOP")
    finally:
        client.loop_stop()
        client.disconnect()
