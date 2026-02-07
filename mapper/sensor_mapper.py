import pandas as pd
import os

"""This class objective is to map every single device available in each room of every floor
of the building with an unique ID once."""
class SensorMapper:
    def __init__(self, config):
        self.cfg = config
        self.dataset_path = config.DATASET_PATH
        self.start_id = 1 

    def build_mapping(self, room_structure):
        mapping_data = []
        global_sensor_id = self.start_id 
        #loop su tutti i piani, le stanze presenti nel dataset 
        for floor, rooms in room_structure.items():
            floor_path = os.path.join(self.dataset_path, floor)
            for room in rooms:
                room_path = os.path.join(floor_path, room)
                if not os.path.exists(room_path): continue
                files = [f for f in os.listdir(room_path) if f.endswith('.csv')]
                files.sort() 
                for f in files:
                    sensor_type = f.split('_')[-1].replace('.csv', '')                    
                    mapping_data.append({
                        "unique_id": global_sensor_id,      
                        "building": self.cfg.BUILDING_ID,
                        "floor": floor,
                        "room": room,
                        "sensor_type": sensor_type,
                        "file_path": os.path.join(room_path, f)
                    })
                    global_sensor_id += 1

        return pd.DataFrame(mapping_data)

    def save_mapping(self, df):
        df.to_csv(self.cfg.MAPPING_FILE_PATH, index=False)
        print(f"Salvataggio Mapping Master in: {self.cfg.MAPPING_FILE_PATH}")