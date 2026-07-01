from abc import ABC, abstractmethod
from pathlib import Path


class BaseIngestor(ABC):
    """Parse a source file and return a list of normalized attribute dicts."""

    @abstractmethod
    def can_handle(self, filename: str) -> bool:
        """Return True if this ingestor handles the given file extension."""

    @abstractmethod
    def parse(self, file_path: Path) -> list[dict]:
        """
        Parse file and return list of records.
        Each record is a flat dict of {attribute_name: value}.
        """
