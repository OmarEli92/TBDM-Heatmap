import pandas as pd
from src.config.settings import Config

class SensorMapper:
    """Genera e gestisce le KEY dei sensori e crea il mapping CSV."""

    def __init__(self, config: Config = Config()):
        self.cfg = config

    def generate_key(self, floor: str, room: str, sensor_type: str, idx: int = 1):
        """Genera la chiave univoca di un sensore."""
        return f"{self.cfg.BUILDING_ID}_{floor}_{room}_{sensor_type}_{idx}"

    def build_mapping(self, room_structure: dict):
        """
        Crea il DataFrame di mapping a partire da una struttura del tipo:
        {
            "4": ["401", "402", "403"],
            "5": ["501", "502"]
        }
        """
        records = []
        for floor, rooms in room_structure.items():
            for room in rooms:
                for sensor in self.cfg.SENSOR_TYPES:
                    key = self.generate_key(floor, room, sensor)
                    records.append({
                        "key": key,
                        "building": self.cfg.BUILDING_ID,
                        "floor": floor,
                        "room": room,
                        "sensor_type": sensor,
                        "sensor_id": 1
                    })
        return pd.DataFrame(records)

    def save_mapping(self, df: pd.DataFrame):
        """Salva il mapping CSV su disco."""
        df.to_csv(self.cfg.MAPPING_PATH, index=False)
