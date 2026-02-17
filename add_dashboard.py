import os
import json
import requests
import configparser
import sys

config = configparser.ConfigParser()
conf_file = "configuration.conf"
if not os.path.exists(conf_file): conf_file = "../configuration.conf"
config.read(conf_file)

TB_URL = config.get("THINGSBOARD", "TB_URL").strip().rstrip("/")
TB_USER = config.get("THINGSBOARD", "TB_USERNAME")
TB_PASS = config.get("THINGSBOARD", "TB_PASSWORD")
BUILDING_NAME = "POLOA"  
DASHBOARD_FILE = "edificio_poloa_dashboard.json"

def get_token():
    try:
        resp = requests.post(f"{TB_URL}/api/auth/login", json={"username": TB_USER, "password": TB_PASS})
        if resp.status_code == 200: return resp.json()["token"]
    except Exception as e: print(f"Login failed: {e}")
    return None

def get_asset_id(token, name):
    """Trova l'ID dell'asset Edificio nel sistema corrente"""
    headers = {"X-Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(f"{TB_URL}/api/tenant/assets", headers=headers, params={"textSearch": name, "pageSize": 1})
        if resp.status_code == 200:
            data = resp.json().get('data')
            if data: return data[0]['id']['id']
    except Exception as e: print(f"Error finding asset: {e}")
    return None

def create_dashboard(token, dashboard_json):
    headers = {"X-Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # 1. Controlla se esiste già una dashboard con lo stesso titolo per non duplicarla
    title = dashboard_json.get("title", "New Dashboard")
    print(f"Checking existing dashboards for '{title}'...")
    resp = requests.get(f"{TB_URL}/api/tenant/dashboards", headers=headers, params={"textSearch": title, "pageSize": 10})
    if resp.status_code == 200 and resp.json()['data']:
        existing_id = resp.json()['data'][0]['id']['id']
        dashboard_json['id'] = {'id': existing_id, 'entityType': 'DASHBOARD'}
        print(f"Updating EXISTING dashboard: {existing_id}")
    else:
        if 'id' in dashboard_json: del dashboard_json['id']
        print("Creating NEW dashboard...")
    url = f"{TB_URL}/api/dashboard"
    resp = requests.post(url, headers=headers, json=dashboard_json)
    if resp.status_code == 200:
        print(" Dashboard saved correctly!")
        return resp.json()['id']['id']
    else:
        print(f"Error during saving: {resp.status_code} - {resp.text}")
        return None

def main():
    if not os.path.exists(DASHBOARD_FILE):
        print(f"File {DASHBOARD_FILE} not found.")
        return

    token = get_token()
    if not token: return

    # 1. Carica il Template JSON
    with open(DASHBOARD_FILE, 'r', encoding='utf-8') as f:
        dash_data = json.load(f)

    # 2. Trova il nuovo ID dell'edificio
    print(f"Cercando l'ID per l'edificio '{BUILDING_NAME}'...")
    building_id = get_asset_id(token, BUILDING_NAME)
    
    if not building_id:
        print(f"ERRORE: Asset '{BUILDING_NAME}' non trovato su ThingsBoard. Esegui prima lo script di importazione CSV.")
        return

    # 3. FIX DINAMICO DEGLI ALIAS
    # Questa parte è cruciale: entra nella configurazione e sostituisce il vecchio ID con quello nuovo
    aliases = dash_data.get('configuration', {}).get('entityAliases', {})
    
    fixed_count = 0
    for alias_id, alias_config in aliases.items():
        # Cerca l'alias che punta a un Asset Singolo (il Root)
        # Filtriamo per nome alias (es. "Root Edificio" o come l'hai chiamato) o per tipo filtro
        filter_conf = alias_config.get('filter', {})
        
        # Se l'alias è di tipo "singleEntity" e punta a un ASSET
        if filter_conf.get('type') == 'singleEntity' and filter_conf.get('singleEntity', {}).get('entityType') == 'ASSET':
            print(f" -> Aggiorno Alias '{alias_config.get('alias')}' con il nuovo ID: {building_id}")
            # SOSTITUISCI L'ID VECCHIO CON QUELLO NUOVO
            filter_conf['singleEntity']['id'] = building_id
            fixed_count += 1

    if fixed_count == 0:
        print("⚠️ ATTENZIONE: Nessun alias 'Root' trovato da aggiornare. Assicurati che l'alias della dashboard sia di tipo 'Single Entity'.")

    # 4. Carica su ThingsBoard
    create_dashboard(token, dash_data)

if __name__ == "__main__":
    main()