from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


# ── Product Family ──────────────────────────────────────────────────────────

class ProductFamilyCreate(BaseModel):
    name: str
    description: str | None = None
    attribute_schema: dict = {}


class ProductFamilyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    attribute_schema: dict | None = None


class ProductFamilyOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    attribute_schema: dict
    created_at: datetime

    class Config:
        from_attributes = True


# ── Product ─────────────────────────────────────────────────────────────────

class ProductCreate(BaseModel):
    name: str
    article_number: str
    family_id: UUID
    attributes: dict = {}


class ProductUpdate(BaseModel):
    name: str | None = None
    attributes: dict | None = None


class ProductDocumentOut(BaseModel):
    id: UUID
    filename: str
    original_filename: str
    source_type: str | None
    doc_category: str | None
    status: str
    error_message: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class ProductAttributeHistoryOut(BaseModel):
    id: UUID
    attribute_key: str
    value: Any
    previous_value: Any
    source_document_id: UUID | None
    source_uri: str | None
    source_name: str | None
    source_type: str | None
    source_system: str | None
    lineage: str | None
    operation: str | None
    owner: str | None
    domain: str | None
    classification: str | None
    changed_by: str | None
    changed_at: datetime

    class Config:
        from_attributes = True


class ProductOut(BaseModel):
    id: UUID
    name: str
    article_number: str
    family_id: UUID
    attributes: dict
    created_at: datetime
    updated_at: datetime
    documents: list[ProductDocumentOut] = []
    attribute_history: list[ProductAttributeHistoryOut] = []

    class Config:
        from_attributes = True


class ProductListItem(BaseModel):
    id: UUID
    name: str
    article_number: str
    family_id: UUID
    attributes: dict
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Ingest ──────────────────────────────────────────────────────────────────

class IngestResult(BaseModel):
    document_id: UUID
    filename: str
    status: str
    records_parsed: int
    message: str
