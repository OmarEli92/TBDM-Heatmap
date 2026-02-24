import pandas as pd
import os
import configparser


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
CONF_FILE = os.path.join(PROJECT_ROOT, "configuration.conf")
MAPPING_FILE = os.path.join(PROJECT_ROOT, "data", "sensor_mapping_master.csv")

config = configparser.ConfigParser()
if not os.path.exists(CONF_FILE):
    print(f"Il file dic onfigurazione non è presente!: {CONF_FILE}")
    CONF_FILE = "configuration.conf" 
config.read(CONF_FILE)
SENSOR_INTERVALS = {k: config.getint("SENSOR_INTERVALS", k) for k in config["SENSOR_INTERVALS"]}

def generate_sensor_keys():
    """
    This method is used to map correctly the ids mapped and the directories.
    """    
    if not os.path.exists(MAPPING_FILE):
        raise FileNotFoundError("Il file di mapping non esiste")

    print(f"Caricamento sensori da: {MAPPING_FILE} ")    
    try:
        df = pd.read_csv(MAPPING_FILE)
    except Exception as e:
        raise ValueError(f"Errore nella lettura del CSV: {e}")
    sensor_keys = []
    for _, row in df.iterrows():
        s_type = row['sensor_type']
        sensor_keys.append({
            "key": str(row['unique_id']),  
            "building": row['building'],
            "floor": str(row['floor']), 
            "room": str(row['room']),
            "sensor_type": s_type,            
            "file": row['file_path'],             
            "interval": SENSOR_INTERVALS.get(s_type, 5) 
        })
        
    return sensor_keys


if __name__ == "__main__":
    keys = generate_sensor_keys()
    print(f"Generati {len(keys)} sensori.")
    print(keys[0])