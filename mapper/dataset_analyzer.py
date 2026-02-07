import os


class DatasetAnalyzer:
    """Utility class used for getting the list of floors and rooms from the dataset"""
    def __init__(self, base_path):
        self.base_path = base_path

    def list_floors(self):
        if not os.path.exists(self.base_path): return []
        return sorted([f for f in os.listdir(self.base_path) 
                       if os.path.isdir(os.path.join(self.base_path, f)) and f.isdigit()])

    def list_rooms(self, floor):
        floor_path = os.path.join(self.base_path, floor)
        if not os.path.exists(floor_path): return []
        return sorted([r for r in os.listdir(floor_path) 
                       if os.path.isdir(os.path.join(floor_path, r))])