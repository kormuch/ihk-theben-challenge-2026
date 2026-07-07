import logging
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.schemas import IngestResult
from app.core.config import settings
from app.core.database import get_db
from app.ingestion.registry import ingest_file
from app.lineage.attribute_history import record_attribute_history
from app.models.product import Product, ProductDocument

logger = logging.getLogger("paul.ingest")

router = APIRouter(prefix="/ingest", tags=["ingest"])

STORAGE = Path(settings.STORAGE_PATH)


@router.post("/upload", response_model=IngestResult)
def upload_and_ingest(
    file: UploadFile = File(...),
    product_id: str = Form(...),
    doc_category: str = Form("Technical"),
    db: Session = Depends(get_db),
):
    """
    Upload a file, save the original, parse it, and merge attributes into the product.
    The original file is always retained regardless of parse outcome.
    """
    try:
        pid = uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid product_id UUID")

    product = db.get(Product, pid)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Determine file type
    filename = file.filename or "unknown"
    suffix = Path(filename).suffix.lower()
    safe_name = f"{uuid.uuid4()}{suffix}"
    dest = STORAGE / safe_name

    # Save original — always, before any parsing
    STORAGE.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    # Create document record
    doc = ProductDocument(
        product_id=pid,
        filename=safe_name,
        original_filename=filename,
        file_path=str(dest),
        source_type=suffix.lstrip("."),
        doc_category=doc_category,
        status="processing",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Parse
    try:
        records = ingest_file(dest)
        # Merge all parsed attributes into product (last record wins on key conflict)
        previous_attributes = dict(product.attributes or {})
        parsed_attributes = {}
        merged_attrs = {**previous_attributes}
        for record in records:
            record_attrs = {k: v for k, v in record.items() if not k.startswith("_")}
            parsed_attributes.update(record_attrs)
            merged_attrs.update(record_attrs)
        product.attributes = merged_attrs
        record_attribute_history(
            db,
            product=product,
            attributes=parsed_attributes,
            previous_attributes=previous_attributes,
            source_document=doc,
            lineage="raw-document -> parser-ingest -> data-layer-postgres -> curated-product",
            operation="document_ingest",
            changed_by="paul-parser-ingest",
        )
        doc.status = "done"
        db.commit()
        logger.info(
            "INGEST OK: %s -> product %s (%s), %d records merged",
            filename, product.article_number, product.name, len(records),
        )
        # Auto-trigger export so product-layer gets updated data immediately
        _trigger_export(db)
        return IngestResult(
            document_id=doc.id,
            filename=filename,
            status="done",
            records_parsed=len(records),
            message=f"Parsed {len(records)} record(s) and merged into product attributes.",
        )
    except Exception as exc:
        doc.status = "error"
        doc.error_message = str(exc)
        db.commit()
        logger.error("INGEST FAILED: %s -> product %s: %s", filename, product_id, exc)
        return IngestResult(
            document_id=doc.id,
            filename=filename,
            status="error",
            records_parsed=0,
            message=f"File saved but parsing failed: {exc}",
        )


@router.get("/documents/{document_id}/download")
def download_original(document_id: uuid.UUID, db: Session = Depends(get_db)):
    """Return the original uploaded file."""
    doc = db.get(ProductDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    file_path = Path(doc.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(
        path=str(file_path),
        filename=download_filename(doc),
        media_type="application/octet-stream",
    )


@router.get("/documents/{document_id}/download/{download_name:path}")
def download_original_named(document_id: uuid.UUID, download_name: str, db: Session = Depends(get_db)):
    """Return the original uploaded file with a filename suffix in the URL for browser previews."""
    doc = db.get(ProductDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    file_path = Path(doc.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(
        path=str(file_path),
        filename=download_filename(doc),
        media_type="application/octet-stream",
    )


def download_filename(doc: ProductDocument) -> str:
    original = doc.original_filename or doc.filename
    if Path(original).suffix:
        return original
    suffix = Path(doc.filename or doc.file_path).suffix
    return f"{original}{suffix}" if suffix else original


def _trigger_export(db: Session) -> None:
    """Auto-trigger export to product-layer shared dir after successful ingestion."""
    try:
        from app.api.export import export_products_json
        export_products_json(db=db)
        logger.info("AUTO-EXPORT: triggered after ingestion, product-layer data updated")
    except Exception as exc:
        logger.error("AUTO-EXPORT FAILED: %s", exc)


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: uuid.UUID, db: Session = Depends(get_db)):
    doc = db.get(ProductDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    # Remove file from disk if it exists
    file_path = Path(doc.file_path)
    if file_path.exists():
        file_path.unlink()
    db.delete(doc)
    db.commit()
