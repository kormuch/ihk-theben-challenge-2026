"""
Stage 2: Specialized Extractor Agents.
Each document type gets its own pre-prompted agent that knows exactly what to look for.
Every extracted field includes a citation — where in the source document the value was found.
Prompts are loaded from prompts.json (editable via UI).
"""
import json
import re

from app.intelligence.llm import call_llm
from app.intelligence.prompts import get_extractor_base_template, get_extractor_instructions


async def extract_from_document(doc_type: str, text_content: str) -> dict:
    """Run the specialized extractor for the given document type. Returns {products: [...]}."""
    content = text_content[:12000]

    prompt = get_extractor_base_template().format(
        doc_type=doc_type,
        specific_instructions=get_extractor_instructions(doc_type),
        content=content,
    )

    raw = await call_llm(prompt)

    # Parse JSON
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError("No JSON in extractor response")

    return json.loads(m.group(0))
