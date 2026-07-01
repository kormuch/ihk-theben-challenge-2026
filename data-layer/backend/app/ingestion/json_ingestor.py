import json
from pathlib import Path

from app.ingestion.base import BaseIngestor


class JsonIngestor(BaseIngestor):
    def can_handle(self, filename: str) -> bool:
        return filename.lower().endswith(".json")

    def parse(self, file_path: Path) -> list[dict]:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        # Accept either a list of objects or a single object
        if isinstance(data, list):
            return [self._flatten(r) for r in data if isinstance(r, dict)]
        elif isinstance(data, dict):
            # Could be {products: [...]} or a single product
            for key in ("products", "items", "data", "records"):
                if key in data and isinstance(data[key], list):
                    return [self._flatten(r) for r in data[key] if isinstance(r, dict)]
            return [self._flatten(data)]
        return []

    def _flatten(self, d: dict, prefix: str = "") -> dict:
        """Flatten one level of nesting — keeps it simple, avoids deep recursion."""
        result = {}
        for k, v in d.items():
            key = f"{prefix}{k}".lower().replace(" ", "_")
            if isinstance(v, dict):
                for sub_k, sub_v in v.items():
                    result[f"{key}_{sub_k}".lower().replace(" ", "_")] = sub_v
            else:
                result[key] = v
        return result
