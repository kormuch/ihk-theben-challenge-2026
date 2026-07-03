"""
API for viewing and editing AI prompts.
Transparency: users can see exactly what the AI is asked for each document type.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.intelligence.prompts import load_prompts, save_prompts

router = APIRouter(prefix="/prompts", tags=["prompts"])


@router.get("/")
def get_prompts():
    """Return the full prompt configuration."""
    return load_prompts()


class PromptUpdate(BaseModel):
    document_types: list[str] | None = None
    classifier_prompt: str | None = None
    extractor_base_template: str | None = None
    extractor_prompts: dict[str, str] | None = None
    generic_extractor_instructions: str | None = None


@router.put("/")
def update_prompts(body: PromptUpdate):
    """Update prompt configuration. Only provided fields are changed."""
    current = load_prompts()

    if body.document_types is not None:
        current["document_types"] = body.document_types
    if body.classifier_prompt is not None:
        current["classifier_prompt"] = body.classifier_prompt
    if body.extractor_base_template is not None:
        current["extractor_base_template"] = body.extractor_base_template
    if body.extractor_prompts is not None:
        current["extractor_prompts"] = body.extractor_prompts
    if body.generic_extractor_instructions is not None:
        current["generic_extractor_instructions"] = body.generic_extractor_instructions

    save_prompts(current)
    return current


class SingleExtractorUpdate(BaseModel):
    instructions: str


@router.put("/extractors/{doc_type}")
def update_single_extractor(doc_type: str, body: SingleExtractorUpdate):
    """Update the extractor prompt for a single document type."""
    current = load_prompts()
    current["extractor_prompts"][doc_type] = body.instructions
    save_prompts(current)
    return {"doc_type": doc_type, "instructions": body.instructions}
