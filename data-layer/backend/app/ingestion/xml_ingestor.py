import xml.etree.ElementTree as ET
from pathlib import Path

from app.ingestion.base import BaseIngestor


class XmlIngestor(BaseIngestor):
    def can_handle(self, filename: str) -> bool:
        return filename.lower().endswith(".xml")

    def parse(self, file_path: Path) -> list[dict]:
        tree = ET.parse(file_path)
        root = tree.getroot()

        # Try to find repeated child elements (likely the product records)
        # Heuristic: the most common child tag is the record element
        child_tags = [child.tag for child in root]
        if not child_tags:
            return []

        most_common_tag = max(set(child_tags), key=child_tags.count)
        records = []
        for elem in root.findall(most_common_tag):
            records.append(self._elem_to_dict(elem))
        return records

    def _elem_to_dict(self, elem: ET.Element) -> dict:
        result = {}
        # Element attributes (e.g. <product id="123">)
        for attr_k, attr_v in elem.attrib.items():
            result[attr_k.lower()] = attr_v
        # Child elements as flat keys
        for child in elem:
            key = child.tag.lower().replace("-", "_").replace(" ", "_")
            # Strip XML namespace if present
            if "}" in key:
                key = key.split("}")[1]
            result[key] = child.text.strip() if child.text else None
        return result
