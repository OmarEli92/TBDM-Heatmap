from src.config.settings import Config
from src.data.dataset_analyzer import DatasetAnalyzer
from src.data.sensor_mapper import SensorMapper
from src.data.geojson_builder import GeoJSONBuilder
import os

def main():
    cfg = Config()

    analyzer = DatasetAnalyzer(cfg.DATASET_PATH)

    floors = analyzer.list_floors()

    room_structure = {}
    for floor in floors:
        rooms = analyzer.list_rooms(floor)
        room_structure[floor] = rooms

    mapper = SensorMapper(cfg)
    mapping_df = mapper.build_mapping(room_structure)
    mapper.save_mapping(mapping_df)

    geo_builder = GeoJSONBuilder(cfg.GEOJSON_PATH, cfg.BUILDING_ID)

    for floor, rooms in room_structure.items():
        geo_builder.create_floor_geojson(floor, rooms, mapping_df)

if __name__ == "__main__":
    main()
