import os
import time
import json
import configparser
import sys
import requests
from pymongo import MongoClient
from datetime import datetime, timezone
import traceback

config = configparser.ConfigParser()
base_dir = os.path.dirname(os.path.abspath(__file__))
conf_file = os.path.join(base_dir, "configuration.conf")

if not os.path.exists(conf_file):
    conf_file = os.path.join(os.path.dirname(base_dir), "configuration.conf")

if os.path.exists(conf_file):
    config.read(conf_file)

def get_conf(env_key, section, conf_key, default_val=None):
    val = os.getenv(env_key)
    if val:
        return val
    if config.has_section(section) and config.has_option(section, conf_key):
        return config.get(section, conf_key)
    return default_val

TB_URL = get_conf("TB_URL", "THINGSBOARD", "TB_URL", "http://thingsboard:9090").strip().rstrip("/")
TB_USER = get_conf("TB_USER", "THINGSBOARD", "TB_USERNAME", "tenant@thingsboard.org")
TB_PASS = get_conf("TB_PASS", "THINGSBOARD", "TB_PASSWORD", "tenant")
MONGO_URI = get_conf("MONGO_URI", "MONGO", "uri", "mongodb://mongo:27017/")
MONGO_DB = get_conf("MONGO_DB", "MONGO", "database", "building_iot")
MONGO_COLLECTION = get_conf("MONGO_COLLECTION", "MONGO", "collection", "aggr_iot_metrics")

STATE_DIR = os.path.join(base_dir, "state")
os.makedirs(STATE_DIR, exist_ok=True)
STATE_FILE = os.path.join(STATE_DIR, "loader_state.json")

BATCH_SIZE = 100
POLL_INTERVAL_FAST = 1
POLL_INTERVAL_SLOW = 5
TOKEN_REFRESH_SECONDS = 3000

print(f"""
   ETL LOADER - MongoDB to ThingsBoard
   ThingsBoard: {TB_URL}
   MongoDB: {MONGO_URI}
   Database: {MONGO_DB}
   Collection: {MONGO_COLLECTION}
""")

def load_watermark():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                ts = data.get("last_ts", 0.0)
                if ts > 0:
                    dt = datetime.fromtimestamp(ts)
                    print(f" Loaded watermark: {dt} ({ts})")
                else:
                    print("Starting from beginning")
                return ts
        except Exception as e:
            print(f" Error loading: {e}")
            return 0.0
    print("No previous state, starting fresh")
    return 0.0

def save_watermark(ts):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(
                {"last_ts": ts, "last_update": datetime.now().isoformat()},
                f,
                indent=2,
            )
    except Exception as e:
        print(f" Error saving: {e}")

global_token = None
token_timestamp = 0
virtual_device_cache = {}

def get_token():
    url = f"{TB_URL}/api/auth/login"
    try:
        response = requests.post(
            url,
            json={"username": TB_USER, "password": TB_PASS},
            timeout=10,
        )
        if response.status_code == 200:
            return response.json().get("token")
        print(f"Login failed: {response.status_code}")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def ensure_token():
    global global_token, token_timestamp
    now = time.time()
    if not global_token or (now - token_timestamp) > TOKEN_REFRESH_SECONDS:
        global_token = get_token()
        token_timestamp = now
        if global_token:
            print("Token refreshed")
        return global_token
    return global_token

def tb_request(method, endpoint, payload=None, params=None):
    global global_token, token_timestamp
    token = ensure_token()
    if not token:
        return None

    headers = {
        "Content-Type": "application/json",
        "X-Authorization": f"Bearer {token}",
    }
    url = f"{TB_URL}{endpoint}"

    for attempt in range(3):
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=payload, timeout=30)
            else:
                return None

            if response.status_code == 401:
                new_tok = get_token()
                if not new_tok:
                    return None
                global_token = new_tok
                token_timestamp = time.time()
                headers["X-Authorization"] = f"Bearer {new_tok}"
                continue

            if response.status_code in (200, 201, 204):
                if response.content and response.content.strip():
                    try:
                        return response.json()
                    except ValueError:
                        return {}
                return {}

            if attempt == 2:
                body = response.text if response.text is not None else ""
                print(f"{endpoint}: HTTP {response.status_code} | body='{body[:200]}'")

        except Exception as e:
            if attempt == 2:
                print(f" {endpoint}: {e}")
            time.sleep(1)

    return None

def parse_aggregation_id(doc_id):
    try:
        doc_id_str = str(doc_id)
        parts = doc_id_str.split("_")
        if len(parts) < 2:
            return None, None
        virtual_device_name = "_".join(parts[:-1])
        timestamp_part = parts[-1]
        return virtual_device_name, timestamp_part
    except Exception as e:
        print(f"Error parsing ID '{doc_id}': {e}")
        return None, None

def get_or_create_virtual_device(device_name, sensor_type, building=None, room=None, floor=None):
    if device_name in virtual_device_cache:
        return virtual_device_cache[device_name]

    search_result = tb_request(
        "GET",
        "/api/tenant/devices",
        params={"textSearch": device_name, "pageSize": 10, "page": 0},
    )

    device_id = None
    if search_result and "data" in search_result:
        for device in search_result["data"]:
            if device.get("name") == device_name:
                device_id = device["id"]["id"]
                print(f"Found: {device_name}")
                break

    if not device_id:
        print(f"Creating: {device_name}")
        payload = {
            "name": device_name,
            "type": "Aggregated Metrics",
            "label": f"Statistics for {sensor_type}",
        }
        create_result = tb_request("POST", "/api/device", payload=payload)
        if create_result and "id" in create_result:
            device_id = create_result["id"]["id"]
            print(f"  Created: {device_name}")
            if device_id and (building or room or floor):
                attributes = {}
                if building:
                    attributes["building"] = building
                if room:
                    attributes["room"] = room
                if floor:
                    attributes["floor"] = floor
                if attributes:
                    attr_endpoint = f"/api/plugins/telemetry/DEVICE/{device_id}/attributes/SERVER_SCOPE"
                    tb_request("POST", attr_endpoint, payload=attributes)
                    print(f"  Attributes set: {attributes}")
        else:
            print(f"  Failed to create: {device_name}")
            return None

    if device_id:
        virtual_device_cache[device_name] = device_id
        return device_id
    return None

def push_telemetry(device_id, timestamp_ms, telemetry_data):
    if not telemetry_data:
        return False
    payload = {"ts": timestamp_ms, "values": telemetry_data}
    endpoint = f"/api/plugins/telemetry/DEVICE/{device_id}/timeseries/TELEMETRY"
    result = tb_request("POST", endpoint, payload=payload)
    return result is not None

def wait_for_services():
    print(f"Waiting for ThingsBoard at {TB_URL}...")
    while True:
        try:
            response = requests.get(f"{TB_URL}/login", timeout=5)
            if response.status_code < 500:
                if get_token():
                    print(" ThingsBoard ready and authenticated")
                    break
        except:
            pass
        time.sleep(5)

    print(f"Waiting for MongoDB at {MONGO_URI}...")
    while True:
        try:
            client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            client.admin.command("ping")
            print(" MongoDB ready")
            break
        except:
            pass
        time.sleep(5)

def main():
    wait_for_services()
    try:
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DB]
        collection = db[MONGO_COLLECTION]
        if MONGO_COLLECTION not in db.list_collection_names():
            print(f"Warning: Collection '{MONGO_COLLECTION}' does not exist yet")
            print("Waiting for Spark to create it...")
        print(f" Connected to {MONGO_DB}.{MONGO_COLLECTION}")
    except Exception as e:
        print(f" Connection error: {e}")
        sys.exit(1)

    last_processed_ts = load_watermark()
    if last_processed_ts == 0:
        print("Starting from beginning of MongoDB data")

    total_documents_sent = 0
    total_errors = 0
    cycle_count = 0
    last_save_time = time.time()

    print("\nBeginning aggregation sync...\n")

    while True:
        try:
            cycle_count += 1
            cycle_start = time.time()

            query = {}
            if last_processed_ts > 0.0:
                watermark_date = datetime.fromtimestamp(last_processed_ts, tz=timezone.utc)
                query = {"window_start": {"$gt": watermark_date}}

            cursor = collection.find(query).sort("window_start", 1).limit(BATCH_SIZE)
            documents = list(cursor)

            if not documents:
                if cycle_count == 1 or cycle_count % 20 == 0:
                    print("No new documents (waiting for Spark aggregations...)")
                time.sleep(POLL_INTERVAL_SLOW)
                continue

            cycle_sent = 0
            cycle_errors = 0
            new_watermark = last_processed_ts

            for doc in documents:
                try:
                    doc_id = doc.get("_id")
                    if not doc_id:
                        print("Document without _id")
                        cycle_errors += 1
                        continue

                    virtual_device_name, _ = parse_aggregation_id(doc_id)
                    if not virtual_device_name:
                        print(f"Cannot parse ID: {doc_id}")
                        cycle_errors += 1
                        continue

                    window_start = doc.get("window_start")
                    if not window_start:
                        print(f"Missing window_start: {doc_id}")
                        cycle_errors += 1
                        continue

                    if isinstance(window_start, datetime):
                        current_ts = window_start.replace(tzinfo=timezone.utc).timestamp()
                    elif isinstance(window_start, (int, float)):
                        current_ts = float(window_start)
                    else:
                        print(f"Invalid window_start type: {type(window_start)}")
                        cycle_errors += 1
                        continue

                    if current_ts > new_watermark:
                        new_watermark = current_ts

                    timestamp_ms = int(current_ts * 1000)

                    telemetry = {}
                    for metric in ["avg", "min", "max", "stddev", "variance", "p99", "p90", "p95"]:
                        value = doc.get(metric)
                        if value is not None:
                            try:
                                telemetry[metric] = float(value)
                            except:
                                pass

                    count_value = doc.get("count")
                    if count_value is not None:
                        try:
                            telemetry["count"] = int(count_value)
                        except:
                            pass

                    for ctx_key in ["building", "floor", "room", "sensor_type"]:
                        value = doc.get(ctx_key)
                        if value is not None:
                            telemetry[f"ctx_{ctx_key}"] = str(value)

                    if not telemetry:
                        print(f"No telemetry in document: {doc_id}")
                        cycle_errors += 1
                        continue

                    building = doc.get("building")
                    room = doc.get("room")
                    floor = doc.get("floor")
                    sensor_type = doc.get("sensor_type", "unknown")

                    device_id = get_or_create_virtual_device(
                        virtual_device_name,
                        sensor_type,
                        building=building,
                        room=room,
                        floor=floor,
                    )

                    if not device_id:
                        print(f"Cannot get device ID for: {virtual_device_name}")
                        cycle_errors += 1
                        total_errors += 1
                        continue

                    success = push_telemetry(device_id, timestamp_ms, telemetry)
                    if success:
                        cycle_sent += 1
                        total_documents_sent += 1
                    else:
                        print(f"Failed to push for: {virtual_device_name}")
                        cycle_errors += 1
                        total_errors += 1

                except Exception as e:
                    print(f"Processing document: {e}")
                    cycle_errors += 1
                    total_errors += 1

            if cycle_sent > 0 or cycle_errors > 0:
                last_processed_ts = new_watermark
                cycle_duration = time.time() - cycle_start
                watermark_dt = datetime.fromtimestamp(new_watermark)
                print(
                    f"\n[CYCLE {cycle_count}] "
                    f"Sent: {cycle_sent}/{len(documents)} docs | "
                    f"Errors: {cycle_errors} | "
                    f"Time: {cycle_duration:.1f}s"
                )
                print(
                    f"  Watermark: {watermark_dt} | "
                    f"Total sent: {total_documents_sent} | "
                    f"Total errors: {total_errors}\n"
                )

            if time.time() - last_save_time > 10:
                save_watermark(last_processed_ts)
                last_save_time = time.time()

            if cycle_sent > 0:
                time.sleep(POLL_INTERVAL_FAST)
            else:
                time.sleep(POLL_INTERVAL_SLOW)

        except KeyboardInterrupt:
            print("\nReceived interrupt signal...")
            break
        except Exception as e:
            print(f"Main loop: {e}")
            traceback.print_exc()
            time.sleep(10)

    save_watermark(last_processed_ts)
    print(f"\nComplete. Total sent: {total_documents_sent}, Errors: {total_errors}")

if __name__ == "__main__":
    main()
