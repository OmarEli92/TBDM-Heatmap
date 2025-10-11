import os
import pandas as pd
from datetime import datetime

class DatasetAnalyzer:
    """Analizza la struttura del dataset Kaggle Smart Building System."""

    def __init__(self, base_path: str):
        self.base_path = base_path

    def list_floors(self):
        """Restituisce la lista dei piani (es: ['4','5','6','7'])."""
        return [f for f in os.listdir(self.base_path) if f.isdigit()]

    def list_rooms(self, floor: str):
        """Elenca le stanze presenti in un determinato piano."""
        floor_path = os.path.join(self.base_path, floor)
        rooms = set()
        for fname in os.listdir(floor_path):
            room_id = fname.split("_")[0]
            rooms.add(room_id)
        return sorted(list(rooms))

    def inspect_file(self, floor: str, file_name: str):
        """Restituisce info base su un file (head, min/max timestamp)."""
        path = os.path.join(self.base_path, floor, file_name)
        df = pd.read_csv(path, names=["timestamp", "value"])
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="s")
        return {
            "rows": len(df),
            "min_time": df["datetime"].min(),
            "max_time": df["datetime"].max()
        }
