import csv
import json
import configparser
import paho.mqtt.client as mqtt
from key_generator import generate_sensor_keys
import threading
import time

config = configparser.ConfigParser()
config.read("configuration.conf")

MQTT_BROKER = config.get("MQTT", "broker")
MQTT_PORT = config.getint("MQTT", "port")
TOPIC_PREFIX = config.get("MQTT", "topic_prefix")
MQTT_QOS = 1
BUILDING_ID = config.get("BUILDING", "id")

# Connessione MQTT
client = mqtt.Client()
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()

running = True

def publish_sensor_data(sensor_info):
    """Simula un sensore real-time che legge il CSV e pubblica continuamente"""
    global running
    try:
        data_rows = []
        with open(sensor_info["file"], newline='') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if len(row) >= 2:
                    data_rows.append((row[0], row[1]))
        
        if not data_rows:
            print(f"Nessun dato in {sensor_info['key']}")
            return
        print(f"[{sensor_info['key']}] Caricati {len(data_rows)} dati dal CSV")
        row_index = 0
        while running:
            timestamp, value = data_rows[row_index]
            try:
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
                print(f"[{sensor_info['key']}] Pubblicati: {payload}")
            except ValueError as e:
                print(f"[{sensor_info['key']}] Errore conversione: {e}")
            row_index = (row_index + 1) % len(data_rows)
    
    except FileNotFoundError:
        print(f"[{sensor_info['key']}] File non trovato: {sensor_info['file']}")
    except Exception as e:
        print(f"[{sensor_info['key']}] Errore: {e}")

def main():
    global running
    sensors = generate_sensor_keys()
    print(f"Trovati {len(sensors)} sensori\n")
    if not sensors:
        print("Nessun sensore trovato!")
        return
    
    threads = []
    
    print("Avvio dei sensori...\n")
    for sensor in sensors:
        thread = threading.Thread(
            target=publish_sensor_data, 
            args=(sensor,), 
            daemon=False,
            name=f"Sensor-{sensor['key']}"
        )
        thread.start()
        threads.append(thread)
    
    print(f" {len(threads)} sensori avviati\n")
    try:
        while running:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        running = False
        print("\n\nPausa...")
        time.sleep(1)  
        client.loop_stop()
        client.disconnect()
        print("Programma terminato.")