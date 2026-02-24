import os
import time
import csv
import json
import configparser
import paho.mqtt.client as mqtt
from operator import itemgetter

config = configparser.ConfigParser()
config.read("configuration.conf")

MQTT_BROKER = config.get("MQTT", "broker")
MQTT_PORT = config.getint("MQTT", "port")
TOPIC_PREFIX = config.get("MQTT", "topic_prefix")
MQTT_QOS = 1

MAPPING_FILE = "data/sensor_mapping_master.csv" 
if config.has_option("DATASET", "mapping_file"):
    MAPPING_FILE = config.get("DATASET", "mapping_file")

# Connessione MQTT
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()  

def load_and_sort_data():
    """Il metodo serve per caricare tutti i CSV in memoria tramite il file di mapping
    e ordinarli per data così da simulare un invio cronologico corretto"""
    all_records = []
    if not os.path.exists(MAPPING_FILE):
        print(f"File mapping non trovato: {MAPPING_FILE}")
        return []
    print(f"Lettura mapping da: {MAPPING_FILE}")
    with open(MAPPING_FILE, 'r', newline='') as mapfile:
        reader = csv.reader(mapfile)
        pos = mapfile.tell()
        line = mapfile.readline()
        mapfile.seek(pos)
        if line and not line[0].isdigit():
            next(reader)
        for row in reader:
            if len(row) < 6: continue
            sensor_id = row[0]
            building = row[1]
            floor = row[2]
            room = row[3]
            sensor_type = row[4]
            raw_path = row[5]
            topic = f"{TOPIC_PREFIX}{floor}/{room}/{sensor_type}"
            file_path = raw_path
            if not os.path.exists(file_path):
                file_path = os.path.join("data", "raw_dataset", floor, room, f"{sensor_type}.csv")
            if os.path.exists(file_path):
                try:
                    with open(file_path, newline='') as csv_data:
                        data_reader = csv.reader(csv_data)
                        for data_row in data_reader:
                            if len(data_row) < 2: continue
                            try:
                                timestamp = int(data_row[0])
                                val = float(data_row[1])

                                payload = {
                                    "timestamp": timestamp,
                                    "building": building,
                                    "floor": floor,
                                    "room": room,
                                    "sensor_type": sensor_type,
                                    "sensor_id": int(sensor_id),
                                    "value": val
                                }
                                all_records.append((timestamp, topic, payload))
                            except ValueError: continue
                except: pass
    all_records.sort(key=itemgetter(0))
    return all_records

def main():
    records = load_and_sort_data()
    total = len(records)
    if total == 0: return
    print(f"Trovati {total} record ordinati. Avvio pubblicazione messaggi...")

    count = 0
    for timestamp, topic, payload in records:
        
        client.publish(topic, json.dumps(payload), qos=MQTT_QOS)
        count += 1
        if count % 100 == 0:
            print(f"Inviati {count}/{total} - {payload['sensor_id']} @ {timestamp}")
        time.sleep(0.005)

    print("Fine")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Fine")
    finally:
        client.loop_stop()
        client.disconnect()