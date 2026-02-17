import os
import time
import json
import requests
from kafka import KafkaProducer

TB_URL = os.getenv("TB_URL", "http://thingsboard:9090").rstrip("/")
TB_USER = os.getenv("TB_USER", "tenant@thingsboard.org")
TB_PASS = os.getenv("TB_PASS", "tenant")

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "iot_sensors")

POLL_SECONDS = float(os.getenv("POLL_SECONDS", "5"))
TB_PAGE_SIZE = int(os.getenv("TB_PAGE_SIZE", "100"))
TB_LIMIT = int(os.getenv("TB_LIMIT", "5000"))
TB_KEYS = [k.strip() for k in os.getenv("TB_KEYS", "co2,humidity,light,temperature,pir").split(",") if k.strip()]

STATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state")
os.makedirs(STATE_DIR, exist_ok=True)
STATE_FILE = os.path.join(STATE_DIR, "watermarks.json")

producer = KafkaProducer(
    bootstrap_servers=[KAFKA_BROKER],
    value_serializer=lambda x: json.dumps(x).encode("utf-8"),
    acks="all",
    retries=10,
    linger_ms=50,
)

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_state(state):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)

_token = None
_token_ts = 0
TOKEN_TTL_SECONDS = 45 * 60  # refresh ~45 min to avoid unnecessary error due to token expiracy

def tb_login():
    url = f"{TB_URL}/api/auth/login"
    r = requests.post(url, json={"username": TB_USER, "password": TB_PASS}, timeout=10)
    r.raise_for_status()
    return r.json()["token"]

def tb_headers():
    global _token, _token_ts
    now = time.time()
    if _token is None or (now - _token_ts) > TOKEN_TTL_SECONDS:
        _token = tb_login()
        _token_ts = now
        print("token refreshed")
    return {"X-Authorization": f"Bearer {_token}"}

def tb_get(path, params=None):
    url = f"{TB_URL}{path}"
    r = requests.get(url, headers=tb_headers(), params=params, timeout=30)
    if r.status_code == 401:
        global _token
        _token = None
        r = requests.get(url, headers=tb_headers(), params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def get_all_devices():
    devices = []
    page = 0
    while True:
        data = tb_get("/api/tenant/devices", params={"pageSize": TB_PAGE_SIZE, "page": page})
        chunk = data.get("data", [])
        if not chunk:
            break
        devices.extend(chunk)
        if len(chunk) < TB_PAGE_SIZE:
            break
        page += 1
    return devices

_meta_cache = {}
def get_device_metadata(device_id):
    if device_id in _meta_cache:
        return _meta_cache[device_id]
    meta = {"building": "Unknown", "floor": "Unknown", "room": "Unknown"}
    try:
        data = tb_get(
            f"/api/plugins/telemetry/DEVICE/{device_id}/values/attributes",
            params={"keys": "building,floor,room"}
        )
        if isinstance(data, list):
            for a in data:
                k = a.get("key")
                v = a.get("value")
                if k in meta and v is not None:
                    meta[k] = v
    except Exception:
        pass
    _meta_cache[device_id] = meta
    return meta

def fetch_timeseries(device_id, keys, start_ms, end_ms):
    if not keys:
        return {}
    params = {
        "keys": ",".join(keys),
        "startTs": start_ms,
        "endTs": end_ms,
        "limit": TB_LIMIT,
        "orderBy": "ASC",
    }
    return tb_get(f"/api/plugins/telemetry/DEVICE/{device_id}/values/timeseries", params=params)

def parse_device_name(device_name: str):
    """
    Atteso: "{sensor_type}_{sensor_id}" es: "co2_12"
    """
    if "_" not in device_name:
        return device_name, 0
    sensor_type, sensor_id = device_name.rsplit("_", 1)
    try:
        return sensor_type, int(sensor_id)
    except ValueError:
        return sensor_type, 0

def main():
    print(f" TB={TB_URL} user={TB_USER}")
    print(f" Kafka={KAFKA_BROKER} topic={KAFKA_TOPIC}")
    print(f" TB_KEYS={TB_KEYS}")

    state = load_state()  # device_id -> last_ts_ms
    last_save = time.time()

    while True:
        now_ms = int(time.time() * 1000)
        cycle_sent = 0
        cycle_devices_with_points = 0
        try:
            devices = get_all_devices()
        except Exception as e:
            print(f"error list of devices: {e}")
            time.sleep(5)
            continue

        for d in devices:
            device_id = d["id"]["id"]
            device_name = d["name"]

            last_ts = int(state.get(device_id, 0))
            start_ts = last_ts + 1
            end_ts = now_ms
            keys = TB_KEYS
            try:
                telemetry = fetch_timeseries(device_id, keys, start_ts, end_ts)
            except Exception as e:
                print(f"error fetch {device_name}: {e}")
                continue
            total_points = sum(len(v) for v in (telemetry or {}).values())
            if total_points == 0:
                continue
            cycle_devices_with_points += 1
            meta = get_device_metadata(device_id)
            _, sensor_id = parse_device_name(device_name)
            max_seen = last_ts
            for key, points in (telemetry or {}).items():
                #for points we mean telemetries
                for p in points:
                    ts_ms = p.get("ts")
                    val = p.get("value")
                    if ts_ms is None or val is None:
                        continue
                    payload = {
                        "timestamp": int(ts_ms / 1000),
                        "building": meta["building"],
                        "floor": meta["floor"],
                        "room": meta["room"],
                        "sensor_type": key,
                        "sensor_id": int(sensor_id),
                        "value": float(val),
                        "device": device_name,
                    }
                    producer.send(KAFKA_TOPIC, value=payload)
                    cycle_sent += 1
                    if ts_ms > max_seen:
                        max_seen = ts_ms
            if max_seen > last_ts:
                state[device_id] = max_seen
            print(f"{device_name} points={total_points} sent_so_far={cycle_sent}")
        if cycle_sent:
            producer.flush()
            print(f" devices_with_points={cycle_devices_with_points} sent={cycle_sent}")
        else:
            print(f" devices_with_points=0 sent=0 (nessun nuovo dato)")
        if time.time() - last_save > 10:
            save_state(state)
            last_save = time.time()
        time.sleep(POLL_SECONDS)

if __name__ == "__main__":
    main()
