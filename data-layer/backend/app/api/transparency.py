"""
Transparency endpoint: exposes the AI pipeline configuration.
Read-only, no DB access, no side effects.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.intelligence.classifier import CLASSIFIER_PROMPT, DOCUMENT_TYPES
from app.intelligence.extractors import EXTRACTOR_PROMPTS, _BASE, _GENERIC_INSTRUCTIONS
from app.intelligence.llm import get_active_config

router = APIRouter(prefix="/analyze", tags=["transparency"])

CONFIDENCE_THRESHOLD = 85


@router.get("/prompts")
def get_prompts():
    """Return all AI prompts, document types, and active LLM configuration."""
    llm_config = get_active_config()

    return JSONResponse(content={
        "pipeline": {
            "description": "Two-stage AI pipeline: classification then extraction",
            "stage_1": "Classifier — identifies document type with confidence score and reasoning",
            "stage_2": "Extractor — extracts structured product data with citations per attribute",
            "confidence_threshold": CONFIDENCE_THRESHOLD,
            "confidence_gate": f">=  {CONFIDENCE_THRESHOLD}% auto-extracts, < {CONFIDENCE_THRESHOLD}% requires human review",
            "text_truncation": {
                "classifier": "8,000 characters",
                "extractor": "12,000 characters",
            },
        },
        "document_types": DOCUMENT_TYPES,
        "prompts": {
            "classifier": CLASSIFIER_PROMPT.replace("{types}", "\n".join(f"- {t}" for t in DOCUMENT_TYPES)).replace("{content}", "<document content>"),
            "extractor_base": _BASE.replace("{doc_type}", "<document type>").replace("{specific_instructions}", "<see per-type instructions below>").replace("{content}", "<document content>"),
            "extractor_per_type": EXTRACTOR_PROMPTS,
            "extractor_fallback": _GENERIC_INSTRUCTIONS,
        },
        "llm": llm_config,
    })
