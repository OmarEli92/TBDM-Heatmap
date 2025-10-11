import os
import json

class FileUtils:
    """Metodi di utilità per gestione file e directory."""

    @staticmethod
    def ensure_dir(path: str):
        os.makedirs(path, exist_ok=True)

    @staticmethod
    def save_json(data: dict, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
