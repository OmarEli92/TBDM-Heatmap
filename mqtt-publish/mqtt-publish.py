import csv
import json
import configparser
import paho.mqtt.client as mqtt
from key_generator import generate_sensor_keys
import time
import os

config = configparser.ConfigParser()
config.read("configuration.conf")

MQTT_BROKER = config.get("MQTT", "broker")
MQTT_PORT = config.getint("MQTT", "port")
MQTT_QOS = 1
BUILDING_ID = config.get("BUILDING", "id")
TOPIC_PREFIX = config.get("MQTT", "topic_prefix") 

#Connessione MQTT 
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()

running = True

def main():
    global running
    try:
        sensors = generate_sensor_keys()
    except Exception as e:
        print(f"Errore caricamento sensori: {e}")
        return
    print(f"Trovati {len(sensors)} sensori nel file contenente il mapping \n")
    if not sensors:
        print("Nessun sensore trovato! Esegui il Mapper prima di eseguire la simulazione.")
        return
    
    print("Avvio simulazione...")

    active_sensors = []
    for sensor_info in sensors:
        try:
            f = open(sensor_info["file"], newline='')
            reader = csv.reader(f)
            active_sensors.append({
                "info": sensor_info,
                "file": f,
                "reader": reader
            })
        except FileNotFoundError:
             print(f"[{sensor_info['key']}] File non trovato: {sensor_info['file']}")
        except Exception as e:
             print(f"Errore thread {sensor_info.get('key')}: {e}")

    try:
        # Simula un sensore real-time che legge il CSV e pubblica continuamente fino a quando non terminano i dati
        while running and active_sensors:
            sensors_to_remove = []
            
            for sensor_obj in active_sensors:
                try:
                    row = next(sensor_obj["reader"])
                    if len(row) >= 2:
                        timestamp, value = row[0], row[1]
                        try:
                            payload = {
                                "timestamp": int(timestamp),
                                "building": BUILDING_ID,
                                "floor": str(sensor_obj["info"]["floor"]),
                                "room": str(sensor_obj["info"]["room"]),
                                "sensor_type": sensor_obj["info"]["sensor_type"],
                                "sensor_id": sensor_obj["info"]["key"], 
                                "value": float(value)
                            }
                            topic = f"{TOPIC_PREFIX}{sensor_obj['info']['floor']}/{sensor_obj['info']['room']}/{sensor_obj['info']['sensor_type']}"
                            client.publish(topic, json.dumps(payload), qos=MQTT_QOS)
                            print(f"[{sensor_obj['info']['key']}] Pubblicati: {payload}")
                        except ValueError as e:
                            print(f"[{sensor_obj['info']['key']}] Errore conversione: {e}")
                
                except StopIteration:
                    sensor_obj["file"].close()
                    sensors_to_remove.append(sensor_obj)
            
            for s in sensors_to_remove:
                active_sensors.remove(s)
            
            time.sleep(0.01)

        print("\nTutti i sensori hanno finito di inviare i dati.")

    except KeyboardInterrupt:
        pass
    finally:
        for s in active_sensors:
            if not s["file"].closed:
                s["file"].close()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        running = False
        print("\nStop")
        time.sleep(1)
        client.loop_stop()
        client.disconnect()
        print("Chiuso.")