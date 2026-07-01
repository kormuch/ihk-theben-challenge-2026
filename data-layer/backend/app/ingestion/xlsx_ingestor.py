from pathlib import Path

import pandas as pd

from app.ingestion.base import BaseIngestor


class XlsxIngestor(BaseIngestor):
    def can_handle(self, filename: str) -> bool:
        return filename.lower().endswith((".xlsx", ".xls"))

    def parse(self, file_path: Path) -> list[dict]:
        # Read first sheet by default; handle multi-sheet by merging
        xl = pd.ExcelFile(file_path)
        records = []
        for sheet in xl.sheet_names:
            df = pd.read_excel(xl, sheet_name=sheet, dtype=str)
            df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
            df.dropna(how="all", inplace=True)
            sheet_records = df.where(pd.notna(df), None).to_dict(orient="records")
            # Tag each record with its sheet origin for traceability
            for r in sheet_records:
                r["_source_sheet"] = sheet
            records.extend(sheet_records)
        return records
