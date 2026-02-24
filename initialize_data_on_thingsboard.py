import os
import time
import csv
import json
import sys
import configparser
from collections import defaultdict
from operator import itemgetter

import paho.mqtt.client as mqtt


config = configparser.ConfigParser()
base_dir = os.path.dirname(os.path.abspath(__file__))
conf_file = os.path.join(base_dir, "configuration.conf")
if not os.path.exists(conf_file):
    conf_file = os.path.join(os.path.dirname(base_dir), "configuration.conf")

if not os.path.exists(conf_file):
    print(" configuration.conf not found")
    sys.exit(1)

config.read(conf_file)

THINGSBOARD_HOST = config.get("THINGSBOARD", "THINGSBOARD_HOST")
THINGSBOARD_PORT = int(config.get("THINGSBOARD", "THINGSBOARD_PORT"))
ACCESS_TOKEN = config.get("THINGSBOARD", "GATEWAY_TOKEN")

mapping_raw = config.get("MAPPING", "mapping_file")
if not os.path.isabs(mapping_raw):
    MAPPING_FILE = os.path.join(base_dir, mapping_raw)
else:
    MAPPING_FILE = mapping_raw

TOPIC_GATEWAY = "v1/gateway/telemetry"


DEFAULT_INTERVALS = {
    "co2": 1,
    "humidity": 1,
    "temperature": 1,
    "luminosity": 1,
    "pir": 2,
}

SENSOR_INTERVALS = dict(DEFAULT_INTERVALS)
if config.has_section("SENSOR_INTERVALS"):
    for k in DEFAULT_INTERVALS.keys():
        if config.has_option("SENSOR_INTERVALS", k):
            SENSOR_INTERVALS[k] = int(config.get("SENSOR_INTERVALS", k))


INTERVAL_KEY_ALIAS = {
    "light": "luminosity",
    "luminosity": "luminosity",
}

def interval_for(sensor_key: str) -> int:
    kk = INTERVAL_KEY_ALIAS.get(sensor_key, sensor_key)
    return int(SENSOR_INTERVALS.get(kk, 1))

client = mqtt.Client()
client.username_pw_set(ACCESS_TOKEN)
client.connect(THINGSBOARD_HOST, THINGSBOARD_PORT, 60)
client.loop_start()


def load_all_records():
    """
    Legge tutti i sensori dal mapping file.
    Ogni record: ts(secondi), device, key, value, building/floor/room/id 
    """
    if not os.path.exists(MAPPING_FILE):
        print(f" mapping file non trovato: {MAPPING_FILE}")
        return []
    records = []

    with open(MAPPING_FILE, "r", newline="") as f:
        reader = csv.reader(f)
        pos = f.tell()
        first = f.readline()
        f.seek(pos)
        if first and not first[0].isdigit():
            next(reader, None)
        for row in reader:
            if len(row) < 6:
                continue
            sensor_id = row[0]          
            building = row[1]
            floor = row[2]
            room = row[3]
            s_type = row[4]             # es: "co2" / "temperature" / "light" / "pir"
            raw_path = row[5]
            device_name = f"{s_type}_{sensor_id}"
            file_path = raw_path
            if not os.path.exists(file_path):
                file_path = os.path.join(base_dir, "data", "raw_dataset", floor, room, f"{s_type}.csv")
            if not os.path.exists(file_path):
                print(f" file dati non trovato per {device_name}: {file_path}")
                continue
            try:
                with open(file_path, "r", newline="") as df:
                    dr = csv.reader(df)
                    for drow in dr:
                        if len(drow) < 2:
                            continue
                        try:
                            ts = int(drow[0])      
                            val = float(drow[1])
                        except ValueError:
                            continue
                        records.append({
                            "ts": ts,
                            "device": device_name,
                            "key": s_type,
                            "value": val,
                            "building": building,
                            "floor": floor,
                            "room": room,
                            "sensor_id": sensor_id,
                        })
            except Exception as e:
                print(f"errore lettura {file_path}: {e}")
    records.sort(key=itemgetter("ts"))
    return records


def select_one_hour_per_stream(records):
    """
    Per OGNI stream (device+key), prendo 1 ora di lettura.
    mi serve per velocizzare la simulazione e non sovraccaricare la RAM avendo comunque
    una window size per le aggregazioni di 10 minuti di default..
    ho comunque abbastanza aggregazioni per dispositivo
    
    """
    by_stream = defaultdict(list)  # (device,key) -> records
    for r in records:
        by_stream[(r["device"], r["key"])].append(r)

    selected = []
    for (dev, key), lst in by_stream.items():
        lst.sort(key=lambda x: x["ts"])
        if not lst:
            continue
        interval = interval_for(key)
        need = 3600 // interval  
        chunk = lst[:need] if len(lst) >= need else lst[:]

        selected.extend(chunk)
    selected.sort(key=itemgetter("ts"))
    return selected


def retimestamp_last_hour(selected):
    """
    Trasforma i timestamp nell'ultima ora odierna.
    Anche qui necessario perchè nel dataset utilizzato le telemetrie risalgono al 2013
    """
    now_s = int(time.time())
    target_start_s = now_s - 3600
    by_stream = defaultdict(list)
    for r in selected:
        by_stream[(r["device"], r["key"])].append(r)
    out = []
    for (dev, key), lst in by_stream.items():
        lst.sort(key=lambda x: x["ts"])
        interval = interval_for(key)
        for i, r in enumerate(lst):
            new_ts_s = target_start_s + i * interval
            rr = dict(r)
            rr["ts_ms"] = new_ts_s * 1000  # Thingsbaord wants ms
            out.append(rr)
    out.sort(key=lambda x: (x["ts_ms"], x["device"], x["key"]))
    return out

def publish_all(retimed):
    total = len(retimed)
    print(f" Invio {total} punti a ThingsBoard (ultima ora).")
    print(f" Intervalli usati: {SENSOR_INTERVALS}  (alias: {INTERVAL_KEY_ALIAS})")
    last_print_ts = None
    for i, r in enumerate(retimed, start=1):
        payload = {
            r["device"]: [{
                "ts": int(r["ts_ms"]),
                "values": { r["key"]: r["value"] }
            }]
        }
        ts_s = int(r["ts_ms"] / 1000)
        ts_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts_s))
        print(
            f"[SEND {i}/{total}] {ts_str} | device={r['device']} key={r['key']} value={r['value']} "
            f"| building={r['building']} floor={r['floor']} room={r['room']}"
        )
        client.publish(TOPIC_GATEWAY, json.dumps(payload), qos=0)
        time.sleep(0.0005)

def main():
    records = load_all_records()
    print(f" Letti {len(records)} record totali (sort globale fatto).")
    selected = select_one_hour_per_stream(records)
    print(f" Selezionati {len(selected)} record = 1 ora per stream (device+key).")
    retimed = retimestamp_last_hour(selected)
    print(f" Retimestamp completato. Primo ts_ms={retimed[0]['ts_ms'] if retimed else 'N/A'}")
    publish_all(retimed)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()
        print(" done")
