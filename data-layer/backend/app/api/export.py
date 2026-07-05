"""
Export endpoint: outputs all products in product-layer format.
This is the bridge between PAUL (data-layer) and Christian's product-layer.

Mapping:
  data-layer               → product-layer
  ─────────────────────────────────────────
  article_number           → sku, id (slugified)
  name                     → name
  family.name              → family
  attributes               → attributes (merged)
  attributes.certifications→ certifications (extracted)
  documents                → documents (with source_uri)
  (generated)              → metadata, quality, lifecycle_status
"""
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("paul.export")

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.models.product import Product, ProductDocument

router = APIRouter(prefix="/export", tags=["export"])

# Map our family names to his family names
FAMILY_MAP = {
    "Timer": "Time Switch",
    "Motion Sensor": "Motion Detector",
    "Room Thermostat": "HVAC Controller",
}

# Attributes that should be pulled out into the top-level certifications array
CERT_KEYS = {"certifications", "rohs_compliance", "reach_compliance", "rohs_compliant", "reach_compliant"}


def _slug(raw: str) -> str:
    text = raw.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "unknown"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _extract_certifications(attributes: dict) -> list[str]:
    """Pull certification-related values out of attributes into a flat list."""
    certs = []
    raw = attributes.get("certifications", "")
    if isinstance(raw, str) and raw:
        # "CE (2014/35/EU LVD), VDE (0620), EN 60669-2-1" → ["CE", "VDE", "EN 60669-2-1"]
        for part in raw.split(","):
            part = part.strip()
            # Simplify: take text before first parenthesis
            short = re.sub(r"\s*\(.*?\)", "", part).strip()
            if short and short not in certs:
                certs.append(short)
    elif isinstance(raw, list):
        certs.extend(raw)

    for key in ("rohs_compliance", "rohs_compliant"):
        val = attributes.get(key, "")
        if val and str(val).lower() in ("true", "compliant", "yes"):
            if "RoHS" not in certs:
                certs.append("RoHS")

    for key in ("reach_compliance", "reach_compliant"):
        val = attributes.get(key, "")
        if val and str(val).lower() in ("true", "compliant", "yes"):
            if "REACH" not in certs:
                certs.append("REACH")

    if not certs:
        certs = ["CE"]  # safe default for Theben products

    return certs


def _to_product_layer(product: Product) -> dict:
    """Convert a data-layer product to product-layer format."""
    family_name = product.family.name if product.family else "Unassigned"
    mapped_family = FAMILY_MAP.get(family_name, family_name)

    # Clean attributes: remove cert-related keys (they go into top-level certifications)
    attrs = dict(product.attributes or {})
    clean_attrs = {k: v for k, v in attrs.items() if k not in CERT_KEYS}

    # Add standard attributes his layer expects
    clean_attrs.setdefault("nominal_voltage", attrs.get("operating_voltage", attrs.get("voltage", "230V")))
    clean_attrs.setdefault("ip_rating", attrs.get("protection_class", attrs.get("ip_protection", "IP20")))

    certifications = _extract_certifications(attrs)

    documents = []
    if product.documents:
        for doc in product.documents:
            documents.append({
                "name": doc.original_filename or doc.filename,
                "type": (doc.doc_category or "datasheet").lower(),
                "source_uri": f"data-layer://documents/{product.article_number}/{doc.filename}",
            })

    created = product.created_at.isoformat() if product.created_at else _utc_now()
    updated = product.updated_at.isoformat() if product.updated_at else _utc_now()

    return {
        "id": _slug(product.article_number),
        "sku": product.article_number,
        "name": product.name,
        "family": mapped_family,
        "lifecycle_status": "active",
        "attributes": clean_attrs,
        "certifications": certifications,
        "documents": documents,
        "metadata": {
            "owner": "Product Data Domain",
            "steward": "product-data-steward@thebenpaul.local",
            "domain": "product",
            "source_system": "paul-data-layer",
            "lineage": "paul-ai-ingest -> data-layer-postgres -> product-layer-json-store",
            "refresh_frequency": "on export",
            "sla": "local MVP, no production SLA",
            "classification": "internal",
            "certification_status": "certified" if len(certifications) > 1 else "needs_review",
            "region": "EU",
        },
        "quality": {"last_validation": None, "status": "unknown", "issues": []},
        "created_at": created,
        "updated_at": updated,
    }


@router.get("/products.json")
def export_products_json(db: Session = Depends(get_db)):
    """Export all products in product-layer format (Christian's schema)."""
    products = (
        db.query(Product)
        .options(joinedload(Product.documents), joinedload(Product.family))
        .all()
    )
    exported = [_to_product_layer(p) for p in products]

    payload = {
        "schema_version": "1.0.0",
        "generated_at": _utc_now(),
        "products": exported,
    }

    # Write to shared location if configured or if path exists
    shared_dir = os.environ.get("PRODUCT_LAYER_DATA_DIR")
    if not shared_dir:
        # Try relative path from project root (works outside Docker)
        candidate = Path(__file__).resolve()
        for _ in range(10):
            candidate = candidate.parent
            if (candidate / "product-layer").is_dir():
                shared_dir = str(candidate / "product-layer" / "data")
                break

    if shared_dir:
        try:
            shared_path = Path(shared_dir) / "products.json"
            shared_path.parent.mkdir(parents=True, exist_ok=True)
            with shared_path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, sort_keys=True)
                f.write("\n")
            payload["_written_to"] = str(shared_path)
            logger.info("EXPORT OK: wrote %d products to %s", len(exported), shared_path)
        except Exception as exc:
            logger.error("EXPORT FAILED: could not write to shared dir %s: %s", shared_dir, exc)
    else:
        logger.warning("EXPORT: no shared product-layer dir found (set PRODUCT_LAYER_DATA_DIR or ensure product-layer/data/ exists)")

    # Mirror to Iceberg (non-blocking)
    try:
        from app.lakehouse.iceberg_writer import write_product_to_iceberg
        iceberg_count = 0
        for product in products:
            pl = _to_product_layer(product)
            if write_product_to_iceberg(
                article_number=pl["sku"],
                product_name=pl["name"],
                family=pl["family"],
                attributes=pl["attributes"],
                certifications=pl["certifications"],
            ):
                iceberg_count += 1
        if iceberg_count:
            logger.info("ICEBERG SYNC: %d/%d products mirrored", iceberg_count, len(products))
            payload["_iceberg_synced"] = iceberg_count
    except Exception as exc:
        logger.warning("ICEBERG SYNC SKIP: %s", exc)

    return JSONResponse(content=payload)
