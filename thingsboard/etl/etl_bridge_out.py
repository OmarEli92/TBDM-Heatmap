import time
import json
import pymongo
import requests
import os

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("MONGO_DB")
COLLECTION_NAME = os.getenv("MONGO_COLLECTION_AGGR") # La collection delle aggregazioni
MAPPING_FILE = "room_mapping.json"
TB_URL = os.getenv("TB_URL")

# Caricamento Token
with open(MAPPING_FILE, "r") as f:
    room_mapping = json.load(f)

client = pymongo.MongoClient(MONGO_URI)
db = client[DB_NAME]
collection = db[COLLECTION_NAME]


def sync_to_thingsboard():
    # Cerchiamo i dati aggregati da Spark non ancora processati
    cursor = collection.find({"processed_by_etl": {"$ne": True}})

    for doc in cursor:
        # Nota: Assicurati che Spark includa il campo 'room' o 'id' nel risultato
        # Se Spark salva il nome della stanza nel campo 'room':
        room_id = doc.get("room")

        if room_id in room_mapping:
            token = room_mapping[room_id]["heatmap_token"]
            url = f"{TB_URL}/api/v1/{token}/telemetry"

            # Prepariamo i dati aggregati (controlla i nomi dei campi prodotti da aggregator.py)
            payload = {
                "avg_value": doc.get("avg"),  # O il nome campo generato da Spark
                "max_value": doc.get("max"),
                "min_value": doc.get("min"),
                "window_start": str(doc.get("window_start"))
            }

            try:
                res = requests.post(url, json=payload, timeout=5)
                if res.status_code == 200:
                    # Usiamo un flag specifico per non interferire con altri processi
                    collection.update_one({"_id": doc["_id"]}, {"$set": {"processed_by_etl": True}})
                    print(f"Inviata aggregazione per {room_id}")
            except Exception as e:
                print(f"Errore: {e}")


if __name__ == "__main__":
    print(f"ETL Bridge avviato. In ascolto su {DB_NAME}.{COLLECTION_NAME}")
    while True:
        sync_to_thingsboard()
        time.sleep(5)