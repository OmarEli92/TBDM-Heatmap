import json
import os

class GeoJSONBuilder:
    """Costruisce un file GeoJSON per ogni piano dell’edificio."""

    def __init__(self, geojson_dir: str, building_id: str):
        self.geojson_dir = geojson_dir
        self.building_id = building_id
        os.makedirs(self.geojson_dir, exist_ok=True)

    def _polygon(self, lon, lat, dx=0.00006, dy=0.00004):
        """Crea un piccolo poligono rettangolare (coordinate finte)."""
        return [
            [lon, lat],
            [lon + dx, lat],
            [lon + dx, lat + dy],
            [lon, lat + dy],
            [lon, lat]
        ]

    def create_floor_geojson(self, floor: str, rooms: list, mapping_df):
        """Genera il GeoJSON per un piano."""
        features = []
        base_lon, base_lat = 9.19, 45.464 

        for i, room in enumerate(rooms):
            lon = base_lon + (i % 5) * 0.0001
            lat = base_lat + (i // 5) * 0.0001
            polygon = self._polygon(lon, lat)

            sensor_ids = mapping_df[
                (mapping_df["floor"] == floor) & (mapping_df["room"] == room)
            ]["key"].tolist()

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
        out_path = os.path.join(self.geojson_dir, f"geojson_floor_{floor}.geojson")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(geojson, f, indent=2)
