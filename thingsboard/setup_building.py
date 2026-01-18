# python
import os
import requests
import json

# --- CONFIGURATION ---
BUILDING_PATH = "../data/raw_dataset"  # Your folder with Floors/Rooms
TB_URL = "http://localhost:9090"  # ThingsBoard web address
# Default tenant administrator credentials
USERNAME = "tenant@thingsboard.org"
PASSWORD = "tenant"


def get_auth_token():
    """Obtain the JWT token to control ThingsBoard via API."""
    url = f"{TB_URL}/api/auth/login"
    payload = {"username": USERNAME, "password": PASSWORD}
    res = requests.post(url, json=payload)
    res.raise_for_status()
    return res.json()["token"]


def create_device_and_get_token(auth_token, device_name):
    """Create a device on ThingsBoard (or find it if it exists) and return its Access Token."""
    headers = {"X-Authorization": f"Bearer {auth_token}"}

    # 1. Create the device (or retrieve it if already present)
    device_url = f"{TB_URL}/api/device"
    device_payload = {"name": device_name, "type": "Room"}
    res_device = requests.post(device_url, json=device_payload, headers=headers)
    res_device.raise_for_status()
    device_id = res_device.json()["id"]["id"]

    # 2. Request the credentials associated with that device
    token_url = f"{TB_URL}/api/device/{device_id}/credentials"
    res_token = requests.get(token_url, headers=headers)
    res_token.raise_for_status()
    return res_token.json()["credentialsId"]


def initialize_building():
    print("--- Starting Building Provisioning ---")
    jwt = get_auth_token()
    final_map = {}

    # Automatic scanning of folders
    for floor in os.listdir(BUILDING_PATH):
        path_floor = os.path.join(BUILDING_PATH, floor)
        if not os.path.isdir(path_floor):
            continue

        for room in os.listdir(path_floor):
            # Create two IDs: one for the real sensor, one for the heatmap device
            real_name = f"{room}_Real"
            heatmap_name = f"{room}_Heatmap"

            print(f"Configuring {room}...")

            token_real = create_device_and_get_token(jwt, real_name)
            token_heatmap = create_device_and_get_token(jwt, heatmap_name)

            final_map[room] = {
                "real_token": token_real,
                "heatmap_token": token_heatmap
            }

    # Save everything to a JSON file
    with open("room_mapping.json", "w") as f:
        json.dump(final_map, f, indent=4)

    print("\n[DONE] File `room_mapping.json` generated successfully!")


if __name__ == "__main__":
    initialize_building()
