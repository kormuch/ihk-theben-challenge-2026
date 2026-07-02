"""
Stage 1: Document Classifier Agent.
Takes raw text content, classifies into a product document type with confidence + reasoning.
"""
import json
import re

from app.intelligence.llm import call_llm

DOCUMENT_TYPES = [
    "Datasheet",
    "Lab Report",
    "Certificate",
    "Software Documentation",
    "Bill of Materials",
    "Marketing Material",
    "Compliance Declaration",
    "Safety Data Sheet",
    "Product Specification",
    "Test Report",
]

CLASSIFIER_PROMPT = """You are a document classifier for an industrial product data platform.
Your job is to identify what type of product document this is.

Possible document types:
{types}

Rules:
- Pick exactly ONE type from the list above, or "Unknown" if none fits.
- Provide a confidence score from 0 to 100.
- Explain WHY you chose this type — reference specific parts of the document (headers, tables, phrases, structure).
- If you detect multiple products in the document, set multi_product to true.

Respond ONLY with valid JSON (no markdown, no explanation outside the JSON):
{{"document_type": "...", "confidence": <0-100>, "reasoning": "...", "multi_product": <true|false>, "detected_products": ["article or name if visible", ...]}}

<document>
{content}
</document>"""


async def classify_document(text_content: str) -> dict:
    """Classify document content. Returns {document_type, confidence, reasoning, multi_product, detected_products}."""
    # Truncate to avoid token limits
    content = text_content[:8000]

    prompt = CLASSIFIER_PROMPT.format(
        types="\n".join(f"- {t}" for t in DOCUMENT_TYPES),
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
