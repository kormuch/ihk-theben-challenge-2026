"""
Prompt configuration loader.
Reads/writes prompts.json so AI prompts are transparent and editable at runtime.
"""
import json
from pathlib import Path

PROMPTS_FILE = Path(__file__).parent / "prompts.json"


def load_prompts() -> dict:
    """Load the full prompts config from disk."""
    with PROMPTS_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_prompts(data: dict) -> None:
    """Write the full prompts config to disk."""
    with PROMPTS_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_document_types() -> list[str]:
    return load_prompts()["document_types"]


def get_classifier_prompt() -> str:
    return load_prompts()["classifier_prompt"]


def get_extractor_base_template() -> str:
    return load_prompts()["extractor_base_template"]


def get_extractor_instructions(doc_type: str) -> str:
    data = load_prompts()
    return data["extractor_prompts"].get(doc_type, data["generic_extractor_instructions"])
