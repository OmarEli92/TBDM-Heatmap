import time
import requests
from collections import defaultdict

TB_URL = "http://localhost:9191"
TB_USER = "tenant@thingsboard.org"
TB_PASS = "tenant"

CANDIDATE_KEYS = ["co2","humidity","temperature","pir","light","luminosity"]
PAGE_SIZE = 100
LIMIT = 10000

def login():
    r = requests.post(f"{TB_URL}/api/auth/login",
                      json={"username": TB_USER, "password": TB_PASS},
                      timeout=10)
    r.raise_for_status()
    return r.json()["token"]

def tb_get(token, path, params=None):
    h = {"X-Authorization": f"Bearer {token}"}
    r = requests.get(f"{TB_URL}{path}", headers=h, params=params, timeout=60)
    r.raise_for_status()
    return r.json()

def list_devices(token):
    devices = []
    page = 0
    while True:
        data = tb_get(token, "/api/tenant/devices", params={"pageSize": PAGE_SIZE, "page": page})
        chunk = data.get("data", [])
        if not chunk:
            break
        devices.extend(chunk)
        if len(chunk) < PAGE_SIZE:
            break
        page += 1
    return devices

def latest_ts_for_device(token, device_id):
    now = int(time.time() * 1000)
    latest = None
    for key in CANDIDATE_KEYS:
        params = {"keys": key, "startTs": 0, "endTs": now, "limit": 1, "orderBy": "DESC"}
        data = tb_get(token, f"/api/plugins/telemetry/DEVICE/{device_id}/values/timeseries", params=params)
        pts = data.get(key, [])
        if pts:
            ts = pts[0]["ts"]
            if latest is None or ts > latest:
                latest = ts
    return latest

def get_timeseries_keys(token, device_id):
    return tb_get(token, f"/api/plugins/telemetry/DEVICE/{device_id}/keys/timeseries") or []

def get_timeseries(token, device_id, keys, start_ms, end_ms):
    if not keys:
        return {}
    params = {
        "keys": ",".join(keys),
        "startTs": start_ms,
        "endTs": end_ms,
        "limit": LIMIT,
        "orderBy": "ASC",
    }
    return tb_get(token, f"/api/plugins/telemetry/DEVICE/{device_id}/values/timeseries", params=params) or {}

def ms_to_str(ms):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ms/1000))

def main():
    token = login()
    devices = list_devices(token)
    print(f"DEVICES totali: {len(devices)}")
   #trova l'ultimo timestamp globale 
    latest_global = None
    for d in devices:
        did = d["id"]["id"]
        lt = latest_ts_for_device(token, did)
        if lt is not None and (latest_global is None or lt > latest_global):
            latest_global = lt

    if latest_global is None:
        print(" Nessuna telemetria trovata su alcun device.")
        return

    end_ms = latest_global
    start_ms = end_ms - 3600_000
    print(f"LATEST {end_ms} -> {ms_to_str(end_ms)}")
    print(f"RANGE {start_ms} -> {end_ms}  ({ms_to_str(start_ms)} -> {ms_to_str(end_ms)})")

    counts = defaultdict(int)
    total_points = 0
    devices_with_points = 0

    for d in devices:
        did = d["id"]["id"]
        name = d["name"]
        keys = get_timeseries_keys(token, did)
        if not keys:
            continue
        data = get_timeseries(token, did, keys, start_ms, end_ms)
        device_points = 0
        for key, points in data.items():
            for p in points:
                ts = p.get("ts")
                val = p.get("value")
                if ts is None:
                    continue
                print(f"{ms_to_str(ts)} | device={name} key={key} value={val}")
                counts[(name, key)] += 1
                total_points += 1
                device_points += 1

        if device_points > 0:
            devices_with_points += 1

    for (dev, key), c in sorted(counts.items(), key=lambda x: (-x[1], x[0][0], x[0][1])):
        print(f"{dev} / {key} -> {c}")
        
    print(f"\nDEVICES WITH TELEMETRIES {devices_with_points}/{len(devices)}")
    print(f"TOTAL TELEMETRIES {total_points}")

if __name__ == "__main__":
    main()
