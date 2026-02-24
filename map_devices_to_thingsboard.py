import csv
import requests
import json
import time
import configparser
import os
import sys

base_dir = os.path.dirname(os.path.abspath(__file__))
conf_file = os.path.join(base_dir, "configuration.conf")

if not os.path.exists(conf_file):
    conf_file = os.path.join(os.path.dirname(base_dir), "configuration.conf")
if not os.path.exists(conf_file):
    print(f"ERRORE: configuration.conf non trovato in {base_dir}")
    sys.exit(1)
config = configparser.ConfigParser()
config.read(conf_file)

try:
    TB_URL = config.get("THINGSBOARD", "TB_URL")
    TB_USERNAME = config.get("THINGSBOARD", "TB_USERNAME")
    TB_PASSWORD = config.get("THINGSBOARD", "TB_PASSWORD")
    mapping_raw = config.get("MAPPING", "mapping_file")
    if not os.path.isabs(mapping_raw):
        CSV_FILE_PATH = os.path.join(base_dir, mapping_raw)
    else:
        CSV_FILE_PATH = mapping_raw
    GATEWAY_TOKEN = config.get("THINGSBOARD", "GATEWAY_TOKEN")
except Exception as e:
    print(f"ERRORE CONFIGURAZIONE: Manca la chiave {e}")
    sys.exit(1)
id_cache = {}


def get_token():
    try:
        resp = requests.post(f"{TB_URL}/api/auth/login", json={"username": TB_USERNAME, "password": TB_PASSWORD}, timeout=10)
        if resp.status_code == 200: return resp.json()["token"]
    except Exception as e: print(f"Login failed: {e}")
    return None


def get_header(token):
    return {"Content-Type": "application/json", "X-Authorization": f"Bearer {token}"}


def create_or_get_asset(token, name, asset_type):
    cache_key = f"{name}_{asset_type}"
    if cache_key in id_cache: return id_cache[cache_key]
    create_url = f"{TB_URL}/api/asset"
    search_url = f"{TB_URL}/api/tenant/assets"
    payload = {"name": name, "type": asset_type}
    try:
        resp = requests.post(create_url, headers=get_header(token), json=payload, timeout=5)
        if resp.status_code == 200:
            asset_id = resp.json()["id"]["id"]
            id_cache[cache_key] = asset_id
            return asset_id
        elif resp.status_code == 400:
            params = {"textSearch": name, "type": asset_type, "page": 0, "pageSize": 1}
            search_resp = requests.get(search_url, headers=get_header(token), params=params, timeout=5)
            if search_resp.status_code == 200:
                data = search_resp.json().get('data')
                if data:
                    asset_id = data[0]['id']['id']
                    id_cache[cache_key] = asset_id
                    return asset_id
    except: pass
    return None


def set_credentials(token, device_id, secret):
    url_get = f"{TB_URL}/api/device/{device_id}/credentials"
    url_save = f"{TB_URL}/api/device/credentials"
    try:
        resp = requests.get(url_get, headers=get_header(token))
        if resp.status_code == 200:
            creds = resp.json()
            creds["credentialsType"] = "ACCESS_TOKEN"
            creds["credentialsId"] = secret
            creds["credentialsValue"] = None
            save_resp = requests.post(url_save, headers=get_header(token), json=creds)
            if save_resp.status_code == 200:
                print(f"Gateway Token impostato correttamente a: {secret}")
            else:
                print(f"Errore salvataggio token: {save_resp.status_code} {save_resp.text}")
        else:
            print(f"Errore recupero credenziali: {resp.status_code}")
    except Exception as e: print(f"Err set_creds: {e}")
    
    
def create_device(token, name, device_type, label, attributes, is_gateway=False):
    url = f"{TB_URL}/api/device"
    payload = {"name": str(name), "type": device_type, "label": label}
    if is_gateway: payload["additionalInfo"] = {"gateway": True}
    dev_id = None
    try:
        resp = requests.post(url, headers=get_header(token), json=payload, timeout=5)
        if resp.status_code == 200:
            dev_id = resp.json()["id"]["id"]
            print(f"Creato: {name}")
        elif resp.status_code == 400:
             search_url = f"{TB_URL}/api/tenant/devices"
             params = {"textSearch": name, "page": 0, "pageSize": 1}
             search_response = requests.get(search_url, headers=get_header(token), params=params, timeout=5)
             if search_response.status_code == 200 and search_response.json().get('data'):
                 dev_id = search_response.json()['data'][0]['id']['id']
                 print(f"Esistente: {name}")
        if dev_id and attributes:
            attr_url = f"{TB_URL}/api/plugins/telemetry/DEVICE/{dev_id}/attributes/SERVER_SCOPE"
            requests.post(attr_url, headers=get_header(token), json=attributes, timeout=5)
    except: pass
    return dev_id

def create_relation(token, from_id, from_type, to_id, to_type):
    url = f"{TB_URL}/api/relation"
    payload = {"from": {"id": from_id, "entityType": from_type}, "to": {"id": to_id, "entityType": to_type}, "type": "Contains"}
    try: requests.post(url, headers=get_header(token), json=payload, timeout=5)
    except: pass
    
    
def main():
    print("Login su ThingsBoard...")
    token = get_token()
    if not token:
        print("Login Fallito! Controlla user/pass nel file conf.")
        return
    print("Configurazione Gateway...")
    gw_id = create_device(token, "Heatmap_Gateway", "gateway", "Main Gateway", {"description": "Auto-generated"}, is_gateway=True)
    if gw_id:
        set_credentials(token, gw_id, GATEWAY_TOKEN)
    else:
        print("Errore creazione Gateway")
    if not os.path.exists(CSV_FILE_PATH):
        print(f"File CSV non trovato: {CSV_FILE_PATH}")
        return
    print("Inizio Mappatura Sensori...")
    with open(CSV_FILE_PATH, mode='r') as f:
        reader = csv.DictReader(f)
        count = 0
        success_count = 0
        for row in reader:
            building_name = row['building']          
            flooroom_name = f"Floor {row['floor']}"   
            room_name = f"Room {row['room']}"     
            device_id = row['unique_id']       
            device_type = row['sensor_type']     
            building_id = create_or_get_asset(token, building_name, "Building")
            floor_id = create_or_get_asset(token, flooroom_name, "Floor")
            room_id = create_or_get_asset(token, room_name, "Room")
            if not building_id or not floor_id or not room_id:
                count += 1
                continue
            create_relation(token, building_id, "ASSET", floor_id, "ASSET")
            create_relation(token, floor_id, "ASSET", room_id, "ASSET")
            attrs = {"building": building_name, "floor": row['floor'], "room": row['room'], "sensor_type": device_type}
            label = f"{device_type.upper()} ({room_name})"
            formatted_name = f"{device_type}_{device_id}"
            d_id = create_device(token, formatted_name, device_type, label, attrs)
            if d_id:
                create_relation(token, room_id, "ASSET", d_id, "DEVICE")
                success_count += 1
            count += 1
            if count % 10 == 0: time.sleep(0.05) 
        print(f"Finito. Righe: {count}, Devices: {success_count}")
        
        
if __name__ == "__main__":
    main()