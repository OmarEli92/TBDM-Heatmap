import os, json, traceback
from fastapi import FastAPI, Request, HTTPException
from kafka import KafkaProducer
from typing import Any, Dict, Optional, List

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "iot_sensors")

producer = KafkaProducer(
    bootstrap_servers=[KAFKA_BROKER],
    value_serializer=lambda x: json.dumps(x, ensure_ascii=False).encode("utf-8"),
    acks="all",
    retries=10,
    linger_ms=20,
)

app = FastAPI()

def to_integer(v: Any, default: int = 0):
    try:
        return int(v)
    except Exception as e:
        print(e)
        return default

def to_float(v: Any) -> Optional[float]:
    try:
        return float(v)
    except Exception as e:
        print(e)
        return None
        
def to_string(d: Dict[str, Any], key: str, default: str = "unknown"):
    value = d.get(key)
    if value is None:
        return default
    return str(value)

def parse_sensor_ID(device_name: str):
    if "_" not in device_name:
        return 0
    sensor_id = device_name.split("_")[1]
    return to_integer(sensor_id, 0)

def is_aggregation_device(device_name: str):
    name = (device_name or "").lower().strip()
    return "heatmap" in name

def normalize_timestamp_ms_to_seconds(ts: Any) -> int:
    if ts is None:
        return 0
    time = to_integer(ts, 0)
    if time >= 1_000_000_000_000:
        return int(time / 1000)
    return time

def extract_thingsboard_events(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [p for p in payload if isinstance(p, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []

def build_kafka_messages(thingsboard_event: Dict[str, Any]) -> List[Dict[str, Any]]:
    message = thingsboard_event.get("msg")
    metadata = thingsboard_event.get("metadata") or {}
    timestamp = thingsboard_event.get("timestamp") or metadata.get("ts")

    if isinstance(message, list):
        sensor_type = to_string(metadata, "ss_sensor_type", to_string(metadata, "deviceType", "unknown"))
        if len(message) == 1:
            message = {sensor_type: message[0]}
        else:
            message = {f"{sensor_type}_{i}": v for i, v in enumerate(message)}

    if not isinstance(message, dict):
        return []
    device_name = to_string(metadata, "deviceName", "")
    if not device_name:
        device_name = to_string(metadata, "device", "")
    if is_aggregation_device(device_name):
        return []
    sensor_id = parse_sensor_ID(device_name)
    building = to_string(metadata, "ss_building", "Unknown")
    floor = to_string(metadata, "ss_floor", "Unknown")
    room = to_string(metadata, "ss_room", "Unknown")
    timestamp_norm = normalize_timestamp_ms_to_seconds(timestamp)
    payload: List[Dict[str, Any]] = []
    for k, v in message.items():
        val = to_float(v)
        if val is None:
            continue
        payload.append(
            {
                "timestamp": timestamp_norm,
                "building": building,
                "floor": floor,
                "room": room,
                "sensor_type": str(k),
                "sensor_id": int(sensor_id),
                "value": float(val),
                "device": device_name,
            }
        )
    return payload

@app.post("/thingsboard")
async def tb(req: Request):
    raw = await req.body()
    print("\nHIT /thingsboard")
    print("Content-Type:", req.headers.get("content-type"))
    print("RAW BODY (bytes):", len(raw))
    print("RAW BODY (text):", raw.decode("utf-8", errors="replace"))
    if not raw:
        raise HTTPException(status_code=400, detail="Empty body")

    try:
        payload = json.loads(raw)
    except Exception as e:
        print("JSON PARSE ERROR")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
    print("PARSED JSON:", json.dumps(payload, indent=2, ensure_ascii=False))
    events = extract_thingsboard_events(payload)
    produced = 0
    for e in events:
        msgs = build_kafka_messages(e)
        for m in msgs:
            print("KAFKA OUT:", json.dumps(m, ensure_ascii=False))
            producer.send(KAFKA_TOPIC, m).get(timeout=10)
            produced += 1
    producer.flush()
    print("OK produced =", produced)
    return {"ok": True, "produced": produced}

@app.post("/publish")
async def publish(req: Request):
    data = await req.json()
    if isinstance(data, list):
        for d in data:
            producer.send(KAFKA_TOPIC, d)
    else:
        producer.send(KAFKA_TOPIC, data)
    producer.flush()
    return {"ok": True}