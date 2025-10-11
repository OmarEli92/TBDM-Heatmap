from dataclasses import dataclass

@dataclass
class Config:
    """Configurazione globale del progetto."""
    BUILDING_ID: str = "POLOA"
    FLOORS: list = ("4", "5", "6", "7")
    SENSOR_TYPES: list = ("co2", "humidity", "temperature", "light", "pir")
    DATASET_PATH: str = "data/raw_dataset"
    MAPPING_PATH: str = "data/mapping.csv"
    GEOJSON_PATH: str = "data/geojson"
