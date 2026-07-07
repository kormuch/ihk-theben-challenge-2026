from typing import Any

from sqlalchemy.orm import Session

from app.models.product import Product, ProductAttributeHistory, ProductDocument


def record_attribute_history(
    db: Session,
    *,
    product: Product,
    attributes: dict[str, Any],
    previous_attributes: dict[str, Any] | None = None,
    source_document: ProductDocument | None = None,
    source_uri: str | None = None,
    source_system: str = "paul-data-layer",
    lineage: str = "raw-document -> paul-ai-ingest -> data-layer-postgres",
    operation: str = "upsert",
    changed_by: str = "paul-ai-ingest",
) -> None:
    previous_attributes = previous_attributes or {}
    for key, value in attributes.items():
        history = ProductAttributeHistory(
            product_id=product.id,
            attribute_key=str(key),
            value=value,
            previous_value=previous_attributes.get(key),
            source_document_id=source_document.id if source_document else None,
            source_uri=source_uri or _document_source_uri(product, source_document),
            source_name=source_document.original_filename if source_document else None,
            source_type=(source_document.doc_category or source_document.source_type) if source_document else None,
            source_system=source_system,
            lineage=lineage,
            operation=operation,
            changed_by=changed_by,
        )
        db.add(history)


def _document_source_uri(product: Product, source_document: ProductDocument | None) -> str | None:
    if not source_document:
        return None
    return f"data-layer://documents/{product.article_number}/{source_document.filename}"
