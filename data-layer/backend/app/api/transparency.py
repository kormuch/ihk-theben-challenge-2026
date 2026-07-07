"""
Transparency endpoint: exposes the AI pipeline configuration.
Read-only, no DB access, no side effects.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.intelligence.llm import get_active_config
from app.intelligence.prompts import load_prompts

router = APIRouter(prefix="/analyze", tags=["transparency"])

CONFIDENCE_THRESHOLD = 85


@router.get("/prompts")
def get_prompts():
    """Return all AI prompts, document types, and active LLM configuration."""
    prompt_config = load_prompts()
    llm_config = get_active_config()
    document_types = prompt_config.get("document_types", [])
    classifier_prompt = str(prompt_config.get("classifier_prompt", ""))
    extractor_base = str(prompt_config.get("extractor_base_template", ""))

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
        "document_types": document_types,
        "prompts": {
            "classifier": classifier_prompt.replace("{types}", "\n".join(f"- {t}" for t in document_types)).replace("{content}", "<document content>"),
            "extractor_base": extractor_base.replace("{doc_type}", "<document type>").replace("{specific_instructions}", "<see per-type instructions below>").replace("{content}", "<document content>"),
            "extractor_per_type": prompt_config.get("extractor_prompts", {}),
            "extractor_fallback": prompt_config.get("generic_extractor_instructions", ""),
        },
        "llm": llm_config,
    })
