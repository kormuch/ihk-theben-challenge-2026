"""
Stage 1: Document Classifier Agent.
Takes raw text content, classifies into a product document type with confidence + reasoning.
Prompts are loaded from prompts.json (editable via UI).
"""
import json
import re

from app.intelligence.llm import call_llm
from app.intelligence.prompts import get_document_types, get_classifier_prompt


async def classify_document(text_content: str) -> dict:
    """Classify document content. Returns {document_type, confidence, reasoning, multi_product, detected_products}."""
    # Truncate to avoid token limits
    content = text_content[:8000]

    prompt = get_classifier_prompt().format(
        types="\n".join(f"- {t}" for t in get_document_types()),
        content=content,
    )

    raw = await call_llm(prompt)

    # Parse JSON from response
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError("No JSON in classifier response")

    result = json.loads(m.group(0))
    result["confidence"] = int(result.get("confidence", 0))
    if result["confidence"] < 0 or result["confidence"] > 100:
        raise ValueError(f"Confidence {result['confidence']} outside 0-100")

    return result
