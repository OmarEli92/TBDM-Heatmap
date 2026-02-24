import json
import os
import pandas as pd

class GeoJSONBuilder:
    """This class is used to build the GEOJson representation of the dataset"""
    def __init__(self, geojson_dir, building_id):
        self.geojson_dir = geojson_dir
        self.building_id = building_id
        os.makedirs(self.geojson_dir, exist_ok=True)

    def _polygon(self, lon, lat, dx=0.00006, dy=0.00004):
        return [[lon, lat], [lon+dx, lat], [lon+dx, lat+dy], [lon, lat+dy], [lon, lat]]

    def create_floor_geojson(self, floor, rooms, mapping_df):
        features = []
        base_lon, base_lat = 9.19, 45.464 
        floor_df = mapping_df[mapping_df['floor'] == floor]
        for i, room in enumerate(rooms):
            lon = base_lon + (i % 5) * 0.00015
            lat = base_lat + (i // 5) * 0.00015
            polygon = self._polygon(lon, lat)
            room_sensors = floor_df[floor_df['room'] == room]
            sensor_ids = room_sensors['unique_id'].tolist() 
            features.append({
                "type": "Feature",
                "properties": {
                    "building": self.building_id,
                    "floor": floor,
                    "room": room,
                    "sensor_ids": sensor_ids 
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [polygon]
                }
            })

        geojson = {"type": "FeatureCollection", "features": features}
        out_path = os.path.join(self.geojson_dir, f"{self.building_id}_{floor}.geojson")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(geojson, f, indent=2)
        print(f"GeoJSON creato: {out_path}")