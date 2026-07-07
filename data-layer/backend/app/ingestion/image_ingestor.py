from pathlib import Path

import pytesseract
from PIL import Image

from app.ingestion.base import BaseIngestor

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}


class ImageIngestor(BaseIngestor):
    def can_handle(self, filename: str) -> bool:
        return Path(filename).suffix.lower() in IMAGE_SUFFIXES

    def parse(self, file_path: Path) -> list[dict]:
        """Extract text from image via OCR and return as single record."""
        img = Image.open(file_path)
        text = pytesseract.image_to_string(img, lang="deu+eng")

        if not text or not text.strip():
            return []

        return [{
            "raw_text": text.strip(),
            "_extraction_method": "ocr",
        }]
