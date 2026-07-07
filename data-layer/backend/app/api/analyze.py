"""
AI-powered document analysis endpoint.
Stage 1: Classify document type (with confidence).
Stage 2: Extract structured product data with citations.
Stage 3 (optional): User confirms → products created/updated.
"""
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.intelligence.classifier import classify_document
from app.intelligence.extractors import extract_from_document
from app.intelligence.text_extract import extract_text
from app.lineage.attribute_history import record_attribute_history
from app.models.product import Product, ProductFamily, ProductDocument

router = APIRouter(prefix="/analyze", tags=["analyze"])

STORAGE = Path(settings.STORAGE_PATH)
CONFIDENCE_THRESHOLD = 80
UNSORTED_FAMILY_NAME = "Unsorted"


def get_or_create_unsorted_family(db: Session) -> ProductFamily:
    family = db.query(ProductFamily).filter_by(name=UNSORTED_FAMILY_NAME).first()
    if family:
        return family
    family = ProductFamily(
        name=UNSORTED_FAMILY_NAME,
        description="Holding family for AI-ingested products that need manual classification.",
        attribute_schema={},
    )
    db.add(family)
    db.commit()
    db.refresh(family)
    return family


def enrich_products_with_family_ids(products: list[dict], db: Session) -> None:
    families_db = {f.name.lower(): f for f in db.query(ProductFamily).all()}
    unsorted = families_db.get(UNSORTED_FAMILY_NAME.lower()) or get_or_create_unsorted_family(db)
    families_db[UNSORTED_FAMILY_NAME.lower()] = unsorted
    for product in products:
        suggestion = str(product.get("family_suggestion") or "").strip()
        match = families_db.get(suggestion.lower()) if suggestion else None
        if match:
            product["family_id"] = str(match.id)
            product["family_name"] = match.name
        else:
            product["family_id"] = str(unsorted.id)
            product["family_name"] = unsorted.name
            product["family_suggestion"] = suggestion or UNSORTED_FAMILY_NAME


@router.post("/")
async def analyze_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload a file → classify → extract → return structured result for user review.
    Does NOT save products yet — that happens on confirm.
    """
    filename = file.filename or "unknown"
    suffix = Path(filename).suffix.lower()
    safe_name = f"{uuid.uuid4()}{suffix}"
    dest = STORAGE / safe_name

    # Save file
    STORAGE.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    # Extract text
    try:
        text_content = extract_text(dest)
    except Exception as exc:
        return {
            "status": "error",
            "filename": filename,
            "stored_as": safe_name,
            "error": f"Could not extract text: {exc}",
        }

    if not text_content.strip():
        return {
            "status": "error",
            "filename": filename,
            "stored_as": safe_name,
            "error": "File appears to be empty or unreadable",
        }

    # Stage 1: Classify
    try:
        classification = await classify_document(text_content)
    except Exception as exc:
        return {
            "status": "error",
            "filename": filename,
            "stored_as": safe_name,
            "error": f"Classification failed: {exc}",
        }

    doc_type = classification.get("document_type", "Unknown")
    confidence = classification.get("confidence", 0)

    result = {
        "status": "classified",
        "filename": filename,
        "stored_as": safe_name,
        "classification": classification,
        "needs_review": confidence < CONFIDENCE_THRESHOLD,
        "extraction": None,
    }

    # Stage 2: Extract (only if confidence is high enough)
    if confidence >= CONFIDENCE_THRESHOLD:
        try:
            extraction = await extract_from_document(doc_type, text_content)
            enrich_products_with_family_ids(extraction.get("products", []), db)
            result["extraction"] = extraction
            result["status"] = "extracted"
        except Exception as exc:
            result["extraction_error"] = str(exc)
            result["status"] = "classified"  # classification succeeded, extraction failed

    return result


class LookupRequest(BaseModel):
    article_numbers: list[str]


@router.post("/lookup")
def lookup_existing(body: LookupRequest, db: Session = Depends(get_db)):
    """Check which article numbers already exist and return their current attributes."""
    result = {}
    for an in body.article_numbers:
        existing = db.query(Product).filter_by(article_number=an).first()
        if existing:
            result[an] = {
                "id": str(existing.id),
                "name": existing.name,
                "family_id": str(existing.family_id),
                "attributes": existing.attributes,
            }
    return result


class ReExtractRequest(BaseModel):
    stored_as: str
    doc_type: str


@router.post("/re-extract")
async def re_extract(
    body: ReExtractRequest,
    db: Session = Depends(get_db),
):
    """
    User overrides the document type → re-run extraction with their chosen type.
    Used when classifier confidence is low or type is wrong.
    """
    file_path = STORAGE / body.stored_as
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Stored file not found")

    try:
        text_content = extract_text(file_path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not extract text: {exc}")

    if not text_content.strip():
        raise HTTPException(status_code=400, detail="File appears to be empty or unreadable")

    try:
        extraction = await extract_from_document(body.doc_type, text_content)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {exc}")

    enrich_products_with_family_ids(extraction.get("products", []), db)

    return {
        "status": "extracted",
        "doc_type": body.doc_type,
        "extraction": extraction,
    }


class ConfirmProduct(BaseModel):
    article_number: str
    name: str
    family_id: str | None = None
    attributes: dict = Field(default_factory=dict)


class ConfirmRequest(BaseModel):
    stored_as: str
    doc_type: str
    products: list[ConfirmProduct] = Field(default_factory=list)


@router.post("/confirm")
def confirm_extraction(
    body: ConfirmRequest,
    db: Session = Depends(get_db),
):
    """
    User reviewed the AI extraction and confirmed. Now create/update products.
    """
    created = []
    updated = []
    errors = []

    for p in body.products:
        if p.family_id:
            try:
                family_id = uuid.UUID(p.family_id)
            except ValueError:
                errors.append({"article_number": p.article_number, "error": "Invalid family_id"})
                continue
        else:
            family_id = get_or_create_unsorted_family(db).id

        if not db.get(ProductFamily, family_id):
            family_id = get_or_create_unsorted_family(db).id

        file_path = STORAGE / body.stored_as

        existing = db.query(Product).filter_by(article_number=p.article_number).first()
        if existing:
            previous_attributes = dict(existing.attributes or {})
            merged = {**(existing.attributes or {}), **p.attributes}
            existing.name = p.name
            existing.family_id = family_id
            existing.attributes = merged
            flag_modified(existing, "attributes")
            db.commit()
            db.refresh(existing)
            updated.append(p.article_number)
        else:
            product = Product(
                name=p.name,
                article_number=p.article_number,
                family_id=family_id,
                attributes=dict(p.attributes),
            )
            db.add(product)
            db.commit()
            db.refresh(product)
            created.append(p.article_number)
            previous_attributes = {}

        # Link document to product
        product_obj = existing or db.query(Product).filter_by(article_number=p.article_number).first()
        source_doc = None
        if product_obj:
            if file_path.exists():
                # Check if document already linked
                source_doc = db.query(ProductDocument).filter_by(
                    filename=body.stored_as, product_id=product_obj.id
                ).first()
                if not source_doc:
                    source_doc = ProductDocument(
                        product_id=product_obj.id,
                        filename=body.stored_as,
                        original_filename=body.stored_as,
                        file_path=str(file_path),
                        source_type=Path(body.stored_as).suffix.lstrip("."),
                        doc_category=body.doc_type,
                        status="done",
                    )
                    db.add(source_doc)
                    db.commit()
                    db.refresh(source_doc)
            record_attribute_history(
                db,
                product=product_obj,
                attributes=dict(p.attributes),
                previous_attributes=previous_attributes,
                source_document=source_doc,
                source_uri=None if source_doc else f"data-layer://ai-ingest/{body.stored_as}",
                lineage="raw-document -> paul-ai-ingest -> data-layer-postgres -> curated-product",
                operation="ai_confirm",
                changed_by="paul-ai-ingest-review",
            )
            db.commit()

    # Auto-export to product-layer after every confirm
    from app.api.export import export_products_json
    try:
        export_products_json(db)
    except Exception:
        pass  # export is best-effort

    # Mirror confirmed products to Iceberg (non-blocking)
    from app.lakehouse.iceberg_writer import write_product_to_iceberg, write_document_lineage
    iceberg_ok = 0
    for p in body.products:
        product_obj = db.query(Product).filter_by(article_number=p.article_number).first()
        if product_obj:
            family_name = product_obj.family.name if product_obj.family else "Unassigned"
            certs = [c for c in p.attributes.get("certifications", "").split(",") if c.strip()] if isinstance(p.attributes.get("certifications"), str) else p.attributes.get("certifications", ["CE"])
            if write_product_to_iceberg(
                article_number=p.article_number,
                product_name=p.name,
                family=family_name,
                attributes=p.attributes,
                certifications=certs if isinstance(certs, list) else ["CE"],
            ):
                iceberg_ok += 1
            # Write document lineage
            file_path = STORAGE / body.stored_as
            if file_path.exists():
                write_document_lineage(
                    document_id=body.stored_as,
                    product_article_number=p.article_number,
                    original_filename=body.stored_as,
                    doc_type=body.doc_type,
                    source_uri=f"data-layer://documents/{p.article_number}/{body.stored_as}",
                )

    return {
        "created": created,
        "updated": updated,
        "errors": errors,
        "iceberg_synced": iceberg_ok,
    }
