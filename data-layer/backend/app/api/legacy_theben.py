import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.export import export_products_json
from app.core.database import get_db
from app.lineage.attribute_history import record_attribute_history
from app.models.product import Product, ProductFamily

router = APIRouter(prefix="/legacy-theben", tags=["legacy-theben"])


class LegacyImportRequest(BaseModel):
    base_url: str | None = None


LEGACY_TIMEOUT = httpx.Timeout(connect=4.0, read=12.0, write=4.0, pool=4.0)


def _base_url(base_url: str | None = None) -> str:
    return (base_url or os.getenv("THEBEN_LEGACY_BASE_URL") or "http://192.168.8.200:8000").rstrip("/")


def _bundled_products_dir() -> Path:
    return Path(os.getenv("THEBEN_BUNDLED_PRODUCTS_DIR") or "/config/theben_legacy_products")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _family(db: Session, category: str | None) -> ProductFamily:
    name = category or "Unsorted"
    family = db.query(ProductFamily).filter(ProductFamily.name == name).first()
    if family:
        return family
    family = ProductFamily(
        name=name,
        description=f"Imported from proprietary Theben REST system category {name}.",
        attribute_schema={},
    )
    db.add(family)
    db.flush()
    return family


async def _fetch_products(base_url: str) -> list[dict[str, Any]]:
    try:
        async with legacy_http_client() as client:
            response = await client.get(f"{base_url}/products")
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        raise legacy_unavailable(exc, f"{base_url}/products") from exc
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("products"), list):
        return [row for row in payload["products"] if isinstance(row, dict)]
    raise HTTPException(status_code=502, detail="Legacy Theben REST system returned an unsupported products payload")


async def _fetch_products_with_boms(base_url: str) -> list[dict[str, Any]]:
    rows = await _fetch_products(base_url)
    enriched = []
    async with legacy_http_client() as client:
        for row in rows:
            article_number = _article_number(row)
            if not article_number or row.get("bom"):
                enriched.append(row)
                continue
            enriched.append(await _with_bom(client, base_url, row, article_number))
    return enriched


async def _with_bom(
    client: httpx.AsyncClient,
    base_url: str,
    row: dict[str, Any],
    article_number: str,
) -> dict[str, Any]:
    next_row = dict(row)
    try:
        bom_payload = await _fetch_bom(client, base_url, article_number)
    except httpx.HTTPStatusError as exc:
        next_row["legacy_theben_bom_error"] = f"HTTP {exc.response.status_code}: {exc.response.text[:500]}"
        return next_row
    except httpx.HTTPError as exc:
        next_row["legacy_theben_bom_error"] = str(exc)
        return next_row

    if isinstance(bom_payload, dict):
        next_row.update({k: v for k, v in bom_payload.items() if k not in {"articleNumber", "articlenumber"}})
        next_row.setdefault("bom", bom_payload.get("bom"))
    elif isinstance(bom_payload, str):
        next_row["bom"] = bom_payload
    next_row["legacy_theben_bom_source"] = f"{base_url}/products/bom?articlenumber={article_number}"
    return next_row


async def _fetch_bom(client: httpx.AsyncClient, base_url: str, article_number: str) -> dict[str, Any] | str:
    # The real proprietary API uses lowercase `articlenumber`; camelCase remains a compatibility fallback.
    errors = []
    for parameter_name in ("articlenumber", "articleNumber"):
        try:
            response = await client.get(f"{base_url}/products/bom", params={parameter_name: article_number})
            response.raise_for_status()
            return _decode_bom_response(response, article_number)
        except httpx.HTTPStatusError as exc:
            errors.append(f"{parameter_name}=... -> HTTP {exc.response.status_code}")
            if exc.response.status_code not in {400, 404, 422}:
                raise
        except httpx.HTTPError as exc:
            errors.append(f"{parameter_name}=... -> {exc}")
            raise
    raise HTTPException(status_code=502, detail=f"Legacy BOM endpoint failed for {article_number}: {'; '.join(errors)}")


def legacy_http_client() -> httpx.AsyncClient:
    # Docker Desktop and corporate shells often inject proxy env vars. The proprietary
    # LAN host must be reached directly, so do not inherit HTTP(S)_PROXY here.
    return httpx.AsyncClient(timeout=LEGACY_TIMEOUT, trust_env=False)


def legacy_unavailable(exc: httpx.HTTPError, url: str) -> HTTPException:
    return HTTPException(
        status_code=502,
        detail={
            "message": "Legacy Theben REST system unavailable",
            "url": url,
            "error": str(exc),
            "hint": "Run this from inside the data-layer backend container: curl -v http://192.168.8.200:8000/products",
            "proxy_handling": "httpx trust_env=false; proxy environment variables are ignored for this LAN call",
        },
    )


def _decode_bom_response(response: httpx.Response, article_number: str) -> dict[str, Any] | str:
    text = response.text.strip()
    if not text:
        return {"articlenumber": article_number, "bom": ""}
    try:
        return response.json()
    except ValueError:
        return {"articlenumber": article_number, "bom": text}


def _article_number(row: dict[str, Any]) -> str:
    return str(row.get("articlenumber") or row.get("articleNumber") or row.get("article_number") or row.get("sku") or "").strip()


def _normalize(row: dict[str, Any], base_url: str) -> dict[str, Any]:
    article_number = _article_number(row)
    if not article_number:
        raise ValueError("missing articlenumber/articleNumber")
    bom_summary = parse_bom_xml(row.get("bom") or "")
    category = row.get("category") or bom_summary.get("product_type") or "Unsorted"
    attributes = {
        "legacy_theben_source": base_url,
        "legacy_theben_article_number": article_number,
        "legacy_theben_category": category,
        "legacy_theben_imported_at": _utc_now(),
        "legacy_theben_raw": row,
    }
    if row.get("legacy_theben_bom_source"):
        attributes["legacy_theben_bom_source"] = row["legacy_theben_bom_source"]
    if row.get("legacy_theben_bom_error"):
        attributes["legacy_theben_bom_error"] = row["legacy_theben_bom_error"]
    if bom_summary:
        attributes.update({
            "legacy_theben_bom_id": bom_summary.get("bom_id"),
            "legacy_theben_bom_version": bom_summary.get("bom_version"),
            "legacy_theben_internal_product_number": bom_summary.get("internal_product_number"),
            "legacy_theben_bom_item_count": len(bom_summary.get("items", [])),
            "legacy_theben_bom_categories": bom_summary.get("categories", []),
            "legacy_theben_bom_suppliers": bom_summary.get("suppliers", []),
            "legacy_theben_bom_items": bom_summary.get("items", []),
        })
    return {
        "article_number": article_number,
        "name": row.get("name") or bom_summary.get("product_name") or article_number,
        "category": category,
        "attributes": attributes,
    }


def parse_bom_xml(xml_text: str) -> dict[str, Any]:
    if not xml_text:
        return {}
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as exc:
        raise ValueError(f"invalid BOM XML: {exc}") from exc

    product = root.find("product")
    items = []
    for item in root.findall("./items/item"):
        parsed = {
            "line": item.attrib.get("line"),
            "internal_part_number": item.attrib.get("internalPartNumber"),
            "part_number": item.attrib.get("partNumber"),
            "quantity": item.attrib.get("quantity"),
            "unit": item.attrib.get("unit"),
            "description": text_or_none(item.find("description")),
            "category": text_or_none(item.find("category")),
            "manufacturer_name": text_or_none(item.find("manufacturerName")),
            "reference": text_or_none(item.find("reference")),
        }
        items.append(parsed)

    categories = sorted({item["category"] for item in items if item.get("category")})
    suppliers = sorted({item["manufacturer_name"] for item in items if item.get("manufacturer_name")})
    return {
        "bom_id": root.attrib.get("id"),
        "bom_version": root.attrib.get("version"),
        "product_name": text_or_none(product.find("name")) if product is not None else None,
        "product_type": text_or_none(product.find("type")) if product is not None else None,
        "internal_product_number": text_or_none(product.find("internalProductNumber")) if product is not None else None,
        "items": items,
        "categories": categories,
        "suppliers": suppliers,
    }


def text_or_none(element) -> str | None:
    if element is None or element.text is None:
        return None
    text = element.text.strip()
    return text or None


def load_bundled_product_rows(directory: Path | None = None) -> list[dict[str, Any]]:
    root = directory or _bundled_products_dir()
    if not root.exists():
        raise HTTPException(status_code=404, detail=f"Bundled Theben product directory not found: {root}")
    rows = []
    for path in sorted(root.glob("*.json")):
        with path.open("r", encoding="utf-8") as handle:
            row = json.load(handle)
        row.setdefault("_source_file", str(path))
        rows.append(row)
    return rows


def upsert_normalized_products(db: Session, rows: list[dict[str, Any]], source: str, source_type: str) -> dict[str, Any]:
    created: list[str] = []
    updated: list[str] = []
    skipped: list[dict[str, str]] = []

    for row in rows:
        try:
            normalized = _normalize(row, source)
        except ValueError as exc:
            skipped.append({"reason": str(exc), "row": str(row)})
            continue
        family = _family(db, normalized["category"])
        product = db.query(Product).filter(Product.article_number == normalized["article_number"]).first()
        previous_attributes = dict(product.attributes or {}) if product else {}
        if product:
            product.name = normalized["name"]
            product.family_id = family.id
            product.attributes = {**previous_attributes, **normalized["attributes"]}
            updated.append(product.article_number)
        else:
            product = Product(
                name=normalized["name"],
                article_number=normalized["article_number"],
                family_id=family.id,
                attributes=normalized["attributes"],
            )
            db.add(product)
            db.flush()
            created.append(product.article_number)

        record_attribute_history(
            db,
            product=product,
            attributes=normalized["attributes"],
            previous_attributes=previous_attributes,
            source_uri=source,
            source_system="theben-layer-bundled-products" if source_type == "bundled_file" else "proprietary-theben-rest",
            lineage=f"{source_type} -> data-layer-postgres -> product-layer-export -> theben-layer-report",
            operation="legacy_rest_import",
            changed_by="theben-layer-import-button",
        )

    db.commit()

    try:
        export_products_json(db)
    except Exception:
        pass

    return {
        "status": "ok",
        "source": source,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "count": len(created) + len(updated),
    }


@router.get("/products")
async def list_legacy_products(base_url: str | None = None):
    url = _base_url(base_url)
    products = await _fetch_products_with_boms(url)
    return {"source": url, "count": len(products), "products": products}


@router.get("/health")
async def legacy_health(base_url: str | None = None):
    url = _base_url(base_url)
    try:
        products = await _fetch_products(url)
    except HTTPException as exc:
        return {
            "status": "unreachable",
            "source": url,
            "detail": exc.detail,
            "container_test": f"curl -v {url}/products",
            "bom_test": f"curl -v '{url}/products/bom?articlenumber=7654126'",
        }
    return {
        "status": "ok",
        "source": url,
        "product_count": len(products),
        "container_test": f"curl -v {url}/products",
        "bom_test": f"curl -v '{url}/products/bom?articlenumber=7654126'",
    }


@router.post("/import-products")
async def import_legacy_products(body: LegacyImportRequest | None = None, db: Session = Depends(get_db)):
    url = _base_url(body.base_url if body else None)
    rows = await _fetch_products_with_boms(url)
    return upsert_normalized_products(db, rows, f"{url}/products", "rest_api")


@router.get("/bundled-products")
def list_bundled_products():
    rows = load_bundled_product_rows()
    products = [_normalize(row, str(row.get("_source_file") or _bundled_products_dir())) for row in rows]
    return {"source": str(_bundled_products_dir()), "count": len(products), "products": products}


@router.post("/import-bundled-products")
def import_bundled_products(db: Session = Depends(get_db)):
    rows = load_bundled_product_rows()
    return upsert_normalized_products(db, rows, str(_bundled_products_dir()), "bundled_file")
