from pathlib import Path

import pdfplumber

from app.ingestion.base import BaseIngestor


class PdfIngestor(BaseIngestor):
    def can_handle(self, filename: str) -> bool:
        return filename.lower().endswith(".pdf")

    def parse(self, file_path: Path) -> list[dict]:
        """
        PDF-Strategie: Tabellenextraktion zuerst, Fallback auf Volltext.
        Originaldatei bleibt immer erhalten — das ist der echte Wert bei PDFs.
        """
        records = []

        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                # Try table extraction first
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        if not table or len(table) < 2:
                            continue
                        headers = [
                            str(h).strip().lower().replace(" ", "_")
                            for h in table[0]
                            if h is not None
                        ]
                        for row in table[1:]:
                            if all(cell is None for cell in row):
                                continue
                            record = {
                                headers[i]: (str(row[i]).strip() if row[i] is not None else None)
                                for i in range(min(len(headers), len(row)))
                            }
                            record["_source_page"] = page_num
                            record["_extraction_method"] = "table"
                            records.append(record)
                else:
                    # Fallback: raw text as a single attribute
                    text = page.extract_text()
                    if text and text.strip():
                        records.append({
                            "raw_text": text.strip(),
                            "_source_page": page_num,
                            "_extraction_method": "text",
                        })

        return records
