import os
import configparser

class Config:
    def __init__(self):
        
        self.PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        conf_path = os.path.join(self.PROJECT_ROOT, "configuration.conf")
        config = configparser.ConfigParser()
        config.read(conf_path)
        
        self.MQTT_BROKER = config.get("MQTT", "broker")
        self.MQTT_PORT = config.getint("MQTT", "port")
        self.BUILDING_ID = config.get("BUILDING", "id")
        raw_dataset_rel = config.get("DATASET", "dir")
        self.DATASET_PATH = os.path.join(self.PROJECT_ROOT, raw_dataset_rel)
        mapping_rel = config.get("MAPPING", "mapping_file")
        self.MAPPING_FILE_PATH = os.path.join(self.PROJECT_ROOT, mapping_rel)
        os.makedirs(os.path.dirname(self.MAPPING_FILE_PATH), exist_ok=True)
        self.SENSOR_INTERVALS = {k: config.getint("SENSOR_INTERVALS", k) for k in config["SENSOR_INTERVALS"]}