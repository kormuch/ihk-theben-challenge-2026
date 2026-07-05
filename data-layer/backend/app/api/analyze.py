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
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.intelligence.classifier import classify_document
from app.intelligence.extractors import extract_from_document
from app.intelligence.text_extract import extract_text
from app.models.product import Product, ProductFamily, ProductDocument

router = APIRouter(prefix="/analyze", tags=["analyze"])

STORAGE = Path(settings.STORAGE_PATH)
CONFIDENCE_THRESHOLD = 85


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
            # Enrich products with existing family IDs
            families_db = {f.name.lower(): f for f in db.query(ProductFamily).all()}
            for product in extraction.get("products", []):
                suggestion = product.get("family_suggestion", "")
                match = families_db.get(suggestion.lower())
                if match:
                    product["family_id"] = str(match.id)
                    product["family_name"] = match.name
                else:
                    product["family_id"] = None
                    product["family_name"] = suggestion
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

    # Enrich with existing family IDs
    families_db = {f.name.lower(): f for f in db.query(ProductFamily).all()}
    for product in extraction.get("products", []):
        suggestion = product.get("family_suggestion", "")
        match = families_db.get(suggestion.lower())
        if match:
            product["family_id"] = str(match.id)
            product["family_name"] = match.name
        else:
            product["family_id"] = None
            product["family_name"] = suggestion

    return {
        "status": "extracted",
        "doc_type": body.doc_type,
        "extraction": extraction,
    }


class ConfirmProduct(BaseModel):
    article_number: str
    name: str
    family_id: str
    attributes: dict = {}


class ConfirmRequest(BaseModel):
    stored_as: str
    doc_type: str
    products: list[ConfirmProduct]


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
        try:
            family_id = uuid.UUID(p.family_id)
        except ValueError:
            errors.append({"article_number": p.article_number, "error": "Invalid family_id"})
            continue

        if not db.get(ProductFamily, family_id):
            errors.append({"article_number": p.article_number, "error": "Family not found"})
            continue

        existing = db.query(Product).filter_by(article_number=p.article_number).first()
        if existing:
            # Merge attributes
            merged = {**existing.attributes, **p.attributes}
            existing.attributes = merged
            db.commit()
            updated.append(p.article_number)
        else:
            product = Product(
                name=p.name,
                article_number=p.article_number,
                family_id=family_id,
                attributes=p.attributes,
            )
            db.add(product)
            db.commit()
            db.refresh(product)
            created.append(p.article_number)

        # Link document to product
        file_path = STORAGE / body.stored_as
        if file_path.exists():
            product_obj = existing or db.query(Product).filter_by(article_number=p.article_number).first()
            if product_obj:
                # Check if document already linked
                existing_doc = db.query(ProductDocument).filter_by(
                    filename=body.stored_as, product_id=product_obj.id
                ).first()
                if not existing_doc:
                    doc = ProductDocument(
                        product_id=product_obj.id,
                        filename=body.stored_as,
                        original_filename=Path(body.stored_as).stem,
                        file_path=str(file_path),
                        source_type=Path(body.stored_as).suffix.lstrip("."),
                        doc_category=body.doc_type,
                        status="done",
                    )
                    db.add(doc)
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
                    original_filename=Path(body.stored_as).stem,
                    doc_type=body.doc_type,
                    source_uri=f"data-layer://documents/{p.article_number}/{body.stored_as}",
                )

    return {
        "created": created,
        "updated": updated,
        "errors": errors,
        "iceberg_synced": iceberg_ok,
    }
