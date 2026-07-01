from pathlib import Path

from app.ingestion.base import BaseIngestor
from app.ingestion.csv_ingestor import CsvIngestor
from app.ingestion.xlsx_ingestor import XlsxIngestor
from app.ingestion.json_ingestor import JsonIngestor
from app.ingestion.xml_ingestor import XmlIngestor
from app.ingestion.pdf_ingestor import PdfIngestor

INGESTORS: list[BaseIngestor] = [
    CsvIngestor(),
    XlsxIngestor(),
    JsonIngestor(),
    XmlIngestor(),
    PdfIngestor(),
]


def get_ingestor(filename: str) -> BaseIngestor | None:
    for ingestor in INGESTORS:
        if ingestor.can_handle(filename):
            return ingestor
    return None


def ingest_file(file_path: Path) -> list[dict]:
    """
    Main entry point: detect format, parse, return records.
    Raises ValueError if no ingestor found for this file type.
    """
    ingestor = get_ingestor(file_path.name)
    if ingestor is None:
        raise ValueError(f"Unsupported file type: {file_path.suffix}")
    return ingestor.parse(file_path)
