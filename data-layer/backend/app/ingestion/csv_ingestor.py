from pathlib import Path

import pandas as pd

from app.ingestion.base import BaseIngestor


class CsvIngestor(BaseIngestor):
    def can_handle(self, filename: str) -> bool:
        return filename.lower().endswith(".csv")

    def parse(self, file_path: Path) -> list[dict]:
        df = pd.read_csv(file_path, dtype=str)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        # Drop completely empty rows
        df.dropna(how="all", inplace=True)
        return df.where(pd.notna(df), None).to_dict(orient="records")
