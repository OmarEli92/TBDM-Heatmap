import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mapper.config.config import Config
from mapper.dataset_analyzer import DatasetAnalyzer
from mapper.sensor_mapper import SensorMapper
from mapper.geojson_builder import GeoJSONBuilder


def main():
    print("Mapping iniziato")
    
    try:
        cfg = Config()
        print("Configurazione caricata.")
    except Exception as e:
        print(f"Errore caricamento config: {e}")
        return
    print(f"Analisi dataset in: {cfg.DATASET_PATH}")
    if not os.path.exists(cfg.DATASET_PATH):
        print(f"ERRORE: La cartella {cfg.DATASET_PATH} non esiste.")
        return
    analyzer = DatasetAnalyzer(cfg.DATASET_PATH)
    floors = analyzer.list_floors()
    room_structure = {}
    for floor in floors:
        rooms = analyzer.list_rooms(floor)
        room_structure[floor] = rooms
        print(f" - Piano {floor}: trovate {len(rooms)} stanze.")
    print("\nGenerazione ID Univoci e Mapping...")
    #Mapping delle stanze e sensori
    mapper = SensorMapper(cfg)
    mapping_df = mapper.build_mapping(room_structure)
    mapper.save_mapping(mapping_df)
    print(f"\nCOMPLETATO! Trovati {len(mapping_df)} sensori totali.")
    base_output_dir = os.path.dirname(cfg.MAPPING_FILE_PATH)
    #Generazione GEOJSON
    geojson_dir = os.path.join(base_output_dir, "geojson")
    geo_builder = GeoJSONBuilder(geojson_dir, cfg.BUILDING_ID)
    for floor, rooms in room_structure.items():
        geo_builder.create_floor_geojson(floor, rooms, mapping_df)
    print(f" -> File GeoJSON salvati in: {geojson_dir}")

if __name__ == "__main__":
    main()