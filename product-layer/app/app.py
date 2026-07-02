#!/usr/bin/env python3
"""Stdlib REST API and static UI server for the Thebenpaul product layer."""

from __future__ import annotations

import argparse
import csv
import html
import io
import json
import os
import random
import re
import socket
import sys
import threading
import time
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
DATA_DIR = Path(os.environ.get("THEBEN_DATA_DIR", str(ROOT / "data")))
STATIC_DIR = ROOT / "static"
STORE_PATH = Path(os.environ.get("THEBEN_STORE_PATH", str(DATA_DIR / "products.json")))
INDEX_PATH = (STATIC_DIR / "index.html").resolve()

JSON = "application/json; charset=utf-8"
CSV_MIME = "text/csv; charset=utf-8"
HTML = "text/html; charset=utf-8"
SVG = "image/svg+xml; charset=utf-8"

PRODUCT_FAMILIES = [
    "Time Switch",
    "Motion Detector",
    "HVAC Controller",
    "KNX Actuator",
    "Energy Meter",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path, default: Any) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return default


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    tmp.replace(path)


class ProductStore:
    """Small file-backed store with a lock so local threaded requests are safe."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = threading.RLock()
        self.products: list[dict[str, Any]] = []
        self.load()

    def load(self) -> None:
        with self.lock:
            payload = load_json(self.path, None)
            if not payload:
                self.products = generate_products(1000)
                self.save()
            elif isinstance(payload, dict):
                self.products = payload.get("products", [])
            elif isinstance(payload, list):
                self.products = payload
            else:
                self.products = []

    def save(self) -> None:
        with self.lock:
            save_json(
                self.path,
                {
                    "schema_version": "1.0.0",
                    "generated_at": utc_now(),
                    "products": self.products,
                },
            )

    def list_products(self, query: dict[str, list[str]], user: dict[str, Any]) -> list[dict[str, Any]]:
        search = query.get("search", [""])[0].strip().lower()
        family = query.get("family", [""])[0].strip().lower()
        status = query.get("status", [""])[0].strip().lower()
        certification = query.get("certification", [""])[0].strip().lower()
        limit = int_or_default(query.get("limit", ["200"])[0], 200, 1, 1000)

        with self.lock:
            products = [apply_access_controls(p, user) for p in self.products if row_allowed(p, user)]

        def matches(product: dict[str, Any]) -> bool:
            text = " ".join(
                [
                    str(product.get("sku", "")),
                    str(product.get("name", "")),
                    str(product.get("family", "")),
                    json.dumps(product.get("attributes", {}), sort_keys=True),
                ]
            ).lower()
            metadata = product.get("metadata", {})
            if search and search not in text:
                return False
            if family and family != str(product.get("family", "")).lower():
                return False
            if status and status != str(metadata.get("certification_status", "")).lower():
                return False
            if certification:
                certs = [str(c).lower() for c in product.get("certifications", [])]
                if certification not in certs:
                    return False
            return True

        return [p for p in products if matches(p)][:limit]

    def get_product(self, product_id: str, user: dict[str, Any]) -> dict[str, Any] | None:
        with self.lock:
            for product in self.products:
                if product.get("id") == product_id:
                    if not row_allowed(product, user):
                        return None
                    return apply_access_controls(product, user)
        return None

    def upsert_product(self, incoming: dict[str, Any]) -> dict[str, Any]:
        product = normalize_product(incoming)
        with self.lock:
            for idx, existing in enumerate(self.products):
                if existing.get("id") == product["id"]:
                    product["created_at"] = existing.get("created_at", product["created_at"])
                    product["updated_at"] = utc_now()
                    self.products[idx] = product
                    self.save()
                    return product
            self.products.append(product)
            self.save()
            return product

    def patch_attributes(self, product_id: str, attributes: dict[str, Any]) -> dict[str, Any] | None:
        with self.lock:
            for product in self.products:
                if product.get("id") == product_id:
                    product.setdefault("attributes", {}).update(attributes)
                    product["updated_at"] = utc_now()
                    self.save()
                    return product
        return None

    def import_products(self, products: list[dict[str, Any]]) -> dict[str, Any]:
        imported = []
        errors = []
        for index, product in enumerate(products):
            try:
                imported.append(self.upsert_product(product))
            except ValueError as exc:
                errors.append({"row": index + 1, "error": str(exc)})
        return {"imported": len(imported), "errors": errors, "products": imported[:20]}


def int_or_default(raw: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def generate_products(count: int) -> list[dict[str, Any]]:
    random.seed(20260708)
    products = []
    for idx in range(1, count + 1):
        family = PRODUCT_FAMILIES[(idx - 1) % len(PRODUCT_FAMILIES)]
        sku = f"THB-{family[:3].upper().replace(' ', '')}-{idx:04d}"
        attributes = family_attributes(family, idx)
        certifications = ["CE", "RoHS", "REACH"]
        if idx % 3 == 0:
            certifications.append("VDE")
        if family == "Energy Meter":
            certifications.append("MID")
        classification = "internal"
        if idx % 11 == 0:
            classification = "confidential"
        products.append(
            {
                "id": sku.lower(),
                "sku": sku,
                "name": f"Thebenpaul {family} {idx:04d}",
                "family": family,
                "lifecycle_status": random.choice(["active", "phase-out", "prototype"]),
                "attributes": attributes,
                "certifications": certifications,
                "documents": [
                    {
                        "name": f"{sku}_datasheet.pdf",
                        "type": "datasheet",
                        "source_uri": f"data-layer://documents/{sku}/datasheet",
                    }
                ],
                "metadata": {
                    "owner": "Product Data Domain",
                    "steward": "product-data-steward@thebenpaul.local",
                    "domain": "product",
                    "source_system": "mock-generator",
                    "lineage": "mock-generator -> product-layer-json-store",
                    "refresh_frequency": "on import",
                    "sla": "local MVP, no production SLA",
                    "classification": classification,
                    "certification_status": "certified" if idx % 7 else "needs_review",
                    "region": random.choice(["EU", "DE", "GLOBAL"]),
                },
                "quality": {"last_validation": None, "status": "unknown", "issues": []},
                "created_at": utc_now(),
                "updated_at": utc_now(),
            }
        )
    return products


def family_attributes(family: str, idx: int) -> dict[str, Any]:
    base = {
        "gtin": f"4003468{idx:06d}",
        "nominal_voltage": "230V",
        "ip_rating": random.choice(["IP20", "IP44", "IP54"]),
        "ambient_temperature": "-20..45 C",
        "co2_kg": round(0.8 + (idx % 25) * 0.07, 2),
        "recyclable_share_pct": 65 + (idx % 28),
        "commercial_price_eur": round(49 + (idx % 200) * 1.75, 2),
    }
    family_specific = {
        "Time Switch": {"channels": 2 + idx % 4, "program_slots": 56 + idx % 64},
        "Motion Detector": {"detection_angle": "180 deg", "range_m": 8 + idx % 12},
        "HVAC Controller": {"control_loops": 1 + idx % 4, "protocol": "Modbus"},
        "KNX Actuator": {"knx_channels": 4 + idx % 8, "bus_current_ma": 12 + idx % 20},
        "Energy Meter": {"measurement_accuracy": "class B", "phases": 1 if idx % 2 else 3},
    }
    base.update(family_specific[family])
    return base


def normalize_product(product: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(product, dict):
        raise ValueError("product must be an object")
    sku = str(product.get("sku") or product.get("id") or "").strip()
    if not sku:
        raise ValueError("sku is required")
    family = str(product.get("family") or "Unassigned").strip()
    now = utc_now()
    metadata = {
        "owner": "Product Data Domain",
        "steward": "product-data-steward@thebenpaul.local",
        "domain": "product",
        "source_system": "product-layer-api",
        "lineage": "product-layer-api",
        "refresh_frequency": "on import",
        "sla": "local MVP, no production SLA",
        "classification": "internal",
        "certification_status": "draft",
        "region": "EU",
    }
    metadata.update(product.get("metadata") or {})
    return {
        "id": slug(product.get("id") or sku),
        "sku": sku,
        "name": str(product.get("name") or sku).strip(),
        "family": family,
        "lifecycle_status": str(product.get("lifecycle_status") or "active"),
        "attributes": dict(product.get("attributes") or {}),
        "certifications": list(product.get("certifications") or []),
        "documents": list(product.get("documents") or []),
        "metadata": metadata,
        "quality": product.get("quality") or {"last_validation": None, "status": "unknown", "issues": []},
        "created_at": product.get("created_at") or now,
        "updated_at": product.get("updated_at") or now,
    }


def slug(raw: Any) -> str:
    text = str(raw).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or f"product-{int(time.time())}"


ACCESS_CONFIG = load_json(CONFIG_DIR / "access_control.json", {})
QUALITY_CONFIG = load_json(CONFIG_DIR / "quality_rules.json", {})


def current_user(headers: Any) -> dict[str, Any]:
    role = headers.get("X-Role") or os.environ.get("THEBEN_DEFAULT_ROLE", "viewer")
    purpose = headers.get("X-Purpose") or "analytics"
    region = headers.get("X-Region") or "EU"
    return {"role": role, "purpose": purpose, "region": region}


def role_permissions(role: str) -> list[str]:
    roles = ACCESS_CONFIG.get("roles", {})
    return roles.get(role, roles.get("viewer", {})).get("permissions", [])


def has_permission(user: dict[str, Any], permission: str) -> bool:
    permissions = role_permissions(user.get("role", "viewer"))
    return "*" in permissions or permission in permissions


def row_allowed(product: dict[str, Any], user: dict[str, Any]) -> bool:
    rules = ACCESS_CONFIG.get("row_level_security", [])
    region = product.get("metadata", {}).get("region")
    for rule in rules:
        if rule.get("field") == "metadata.region" and rule.get("mode") == "match_user_region":
            if region not in (None, "GLOBAL", user.get("region")) and not has_permission(user, "product:read_all_regions"):
                return False
    return True


def apply_access_controls(product: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    cloned = json.loads(json.dumps(product))
    classification = cloned.get("metadata", {}).get("classification", "internal")
    masking = ACCESS_CONFIG.get("masking", {})
    for field in masking.get(classification, []):
        if not has_permission(user, f"unmask:{field}"):
            mask_field(cloned, field)
    return cloned


def mask_field(product: dict[str, Any], dotted: str) -> None:
    current = product
    parts = dotted.split(".")
    for part in parts[:-1]:
        current = current.get(part, {})
        if not isinstance(current, dict):
            return
    if parts[-1] in current:
        current[parts[-1]] = "***masked***"


def validate_product(product: dict[str, Any]) -> dict[str, Any]:
    issues = []
    attributes = product.get("attributes", {})
    metadata = product.get("metadata", {})
    required_metadata = QUALITY_CONFIG.get("required_metadata", [])
    for field in required_metadata:
        if not metadata.get(field):
            issues.append({"severity": "error", "field": f"metadata.{field}", "message": "required metadata missing"})

    generic = QUALITY_CONFIG.get("required_attributes", {}).get("*", [])
    family = QUALITY_CONFIG.get("required_attributes", {}).get(product.get("family"), [])
    for attr in generic + family:
        if attributes.get(attr) in (None, ""):
            issues.append({"severity": "error", "field": f"attributes.{attr}", "message": "required attribute missing"})

    for rule in QUALITY_CONFIG.get("numeric_ranges", []):
        name = rule.get("attribute")
        if name in attributes:
            try:
                value = float(attributes[name])
            except (TypeError, ValueError):
                issues.append({"severity": "error", "field": f"attributes.{name}", "message": "must be numeric"})
                continue
            if value < float(rule.get("min", value)) or value > float(rule.get("max", value)):
                issues.append({"severity": "warning", "field": f"attributes.{name}", "message": "outside configured range"})

    status = "certified" if not issues else "needs_review"
    return {"status": status, "issues": issues, "checked_at": utc_now()}


def summary(products: list[dict[str, Any]]) -> dict[str, Any]:
    families: dict[str, int] = {}
    statuses: dict[str, int] = {}
    certifications: dict[str, int] = {}
    classifications: dict[str, int] = {}
    for product in products:
        families[product.get("family", "unknown")] = families.get(product.get("family", "unknown"), 0) + 1
        status = product.get("metadata", {}).get("certification_status", "unknown")
        statuses[status] = statuses.get(status, 0) + 1
        classification = product.get("metadata", {}).get("classification", "unknown")
        classifications[classification] = classifications.get(classification, 0) + 1
        for cert in product.get("certifications", []):
            certifications[cert] = certifications.get(cert, 0) + 1
    return {
        "total_products": len(products),
        "families": families,
        "certification_statuses": statuses,
        "certifications": certifications,
        "classifications": classifications,
        "generated_at": utc_now(),
    }


def passport(product: dict[str, Any]) -> dict[str, Any]:
    attrs = product.get("attributes", {})
    return {
        "passport_version": "0.1.0",
        "product": {
            "sku": product.get("sku"),
            "name": product.get("name"),
            "family": product.get("family"),
            "lifecycle_status": product.get("lifecycle_status"),
        },
        "identity": {
            "gtin": attrs.get("gtin"),
            "source_documents": product.get("documents", []),
            "lineage": product.get("metadata", {}).get("lineage"),
        },
        "compliance": {
            "certifications": product.get("certifications", []),
            "certification_status": product.get("metadata", {}).get("certification_status"),
            "regulatory_scope": ["RoHS", "REACH", "ESPR", "Data Act", "CRA-ready metadata placeholder"],
        },
        "sustainability": {
            "co2_kg": attrs.get("co2_kg"),
            "recyclable_share_pct": attrs.get("recyclable_share_pct"),
        },
        "governance": product.get("metadata", {}),
        "quality": product.get("quality", {}),
        "attributes": attrs,
    }


def openapi_spec(host: str) -> dict[str, Any]:
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Thebenpaul Product Layer API",
            "version": "0.1.0",
            "description": "Local MVP REST API for product data, validation, exports, and Digital Product Passport previews.",
        },
        "servers": [{"url": f"http://{host}"}],
        "paths": {
            "/api/products": {
                "get": {"summary": "List products with search and filters"},
                "post": {"summary": "Create or replace a product"},
            },
            "/api/products/{id}": {"get": {"summary": "Read one product"}},
            "/api/products/{id}/attributes": {"patch": {"summary": "Patch dynamic product attributes"}},
            "/api/import": {"post": {"summary": "Import products from JSON array or CSV"}},
            "/api/validation/status": {"get": {"summary": "Run product quality validation"}},
            "/api/summary": {"get": {"summary": "Visualization-ready aggregate summary"}},
            "/api/passport/{id}": {"get": {"summary": "Digital Product Passport JSON preview"}},
            "/api/export/products.csv": {"get": {"summary": "CSV export"}},
            "/api/export/passport/{id}.html": {"get": {"summary": "Printable/PDF-friendly passport HTML"}},
            "/api/export/passport/{id}.svg": {"get": {"summary": "SVG picture export for a product passport"}},
            "/api/openapi.json": {"get": {"summary": "OpenAPI JSON"}},
        },
        "components": {
            "securitySchemes": {
                "LocalRoleHeaders": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-Role",
                    "description": "Local MVP role selector: viewer, editor, steward, admin.",
                }
            }
        },
        "security": [{"LocalRoleHeaders": []}],
    }


class Handler(SimpleHTTPRequestHandler):
    server_version = "ThebenpaulProductLayer/0.1"

    def translate_path(self, path: str) -> str:
        parsed = urlparse(path)
        clean = unquote(parsed.path).lstrip("/")
        if clean in ("", "index.html"):
            return str(INDEX_PATH)
        static_root = STATIC_DIR.resolve()
        candidate = (static_root / clean).resolve()
        if candidate == static_root or static_root not in candidate.parents:
            return str(INDEX_PATH)
        return str(candidate)

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), fmt % args))

    @property
    def store(self) -> ProductStore:
        return self.server.store  # type: ignore[attr-defined]

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        user = current_user(self.headers)

        if path == "/health":
            return self.send_json({"status": "ok", "service": "product-layer", "time": utc_now()})
        if path == "/docs":
            return self.send_bytes(render_docs(self.headers.get("Host", "localhost")), HTML)
        if path == "/api/openapi.json":
            return self.send_json(openapi_spec(self.headers.get("Host", "localhost")))
        if path == "/api/products":
            return self.send_json({"products": self.store.list_products(query, user)})
        if path.startswith("/api/products/"):
            product_id = path.removeprefix("/api/products/")
            product = self.store.get_product(product_id, user)
            return self.send_json_or_404(product, "product not found")
        if path == "/api/validation/status":
            products = self.store.list_products(query or {"limit": ["1000"]}, user)
            results = []
            for product in products:
                result = validate_product(product)
                results.append({"id": product["id"], "sku": product["sku"], **result})
            counts = {"certified": 0, "needs_review": 0}
            for result in results:
                counts[result["status"]] = counts.get(result["status"], 0) + 1
            return self.send_json({"counts": counts, "results": results})
        if path == "/api/summary":
            products = self.store.list_products({"limit": ["1000"]}, user)
            return self.send_json(summary(products))
        if path.startswith("/api/passport/"):
            product_id = path.removeprefix("/api/passport/")
            product = self.store.get_product(product_id, user)
            return self.send_json_or_404(passport(product) if product else None, "product not found")
        if path == "/api/export/products.csv":
            products = self.store.list_products({"limit": ["1000"]}, user)
            return self.send_bytes(products_csv(products), CSV_MIME, "products.csv")
        if path.startswith("/api/export/passport/") and path.endswith(".html"):
            product_id = path.removeprefix("/api/export/passport/").removesuffix(".html")
            product = self.store.get_product(product_id, user)
            return self.send_bytes(passport_html(product) if product else not_found_html("product not found"), HTML)
        if path.startswith("/api/export/passport/") and path.endswith(".svg"):
            product_id = path.removeprefix("/api/export/passport/").removesuffix(".svg")
            product = self.store.get_product(product_id, user)
            return self.send_bytes(passport_svg(product) if product else not_found_svg("product not found"), SVG)
        return super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        user = current_user(self.headers)
        if parsed.path == "/api/products":
            if not has_permission(user, "product:write"):
                return self.send_error_json(HTTPStatus.FORBIDDEN, "missing product:write permission")
            try:
                product = self.store.upsert_product(self.read_json())
            except ValueError as exc:
                return self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
            return self.send_json({"product": product}, HTTPStatus.CREATED)
        if parsed.path == "/api/import":
            if not has_permission(user, "product:import"):
                return self.send_error_json(HTTPStatus.FORBIDDEN, "missing product:import permission")
            content_type = self.headers.get("Content-Type", "")
            raw = self.read_body()
            try:
                products = parse_import_payload(raw, content_type)
            except ValueError as exc:
                return self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
            return self.send_json(self.store.import_products(products), HTTPStatus.CREATED)
        return self.send_error_json(HTTPStatus.NOT_FOUND, "endpoint not found")

    def do_PATCH(self) -> None:
        parsed = urlparse(self.path)
        user = current_user(self.headers)
        if parsed.path.startswith("/api/products/") and parsed.path.endswith("/attributes"):
            if not has_permission(user, "product:write"):
                return self.send_error_json(HTTPStatus.FORBIDDEN, "missing product:write permission")
            product_id = parsed.path.removeprefix("/api/products/").removesuffix("/attributes").rstrip("/")
            payload = self.read_json()
            attributes = payload.get("attributes", payload)
            if not isinstance(attributes, dict):
                return self.send_error_json(HTTPStatus.BAD_REQUEST, "attributes object required")
            product = self.store.patch_attributes(product_id, attributes)
            return self.send_json_or_404({"product": product} if product else None, "product not found")
        return self.send_error_json(HTTPStatus.NOT_FOUND, "endpoint not found")

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.common_headers(JSON)
        self.end_headers()

    def read_body(self) -> bytes:
        length = int_or_default(self.headers.get("Content-Length", "0"), 0, 0, 20_000_000)
        return self.rfile.read(length)

    def read_json(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.read_body().decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("JSON object required")
        return payload

    def send_json_or_404(self, payload: Any, message: str) -> None:
        if payload is None:
            self.send_error_json(HTTPStatus.NOT_FOUND, message)
        else:
            self.send_json(payload)

    def send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_bytes(json.dumps(payload, indent=2, sort_keys=True).encode("utf-8"), JSON, status=status)

    def send_error_json(self, status: HTTPStatus, message: str) -> None:
        self.send_json({"error": message, "status": int(status)}, status)

    def send_bytes(
        self,
        payload: str | bytes,
        content_type: str,
        filename: str | None = None,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        self.send_response(status)
        self.common_headers(content_type)
        self.send_header("Content-Length", str(len(payload)))
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(payload)

    def common_headers(self, content_type: str) -> None:
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Role, X-Purpose, X-Region")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
        self.send_header("Cache-Control", "no-store")


def parse_import_payload(raw: bytes, content_type: str) -> list[dict[str, Any]]:
    text = raw.decode("utf-8-sig")
    if "csv" in content_type or text.lstrip().lower().startswith("sku,"):
        reader = csv.DictReader(io.StringIO(text))
        products = []
        for row in reader:
            attributes: dict[str, Any] = {}
            metadata: dict[str, Any] = {}
            product: dict[str, Any] = {}
            for key, value in row.items():
                if key is None:
                    continue
                value = value.strip() if isinstance(value, str) else value
                if key.startswith("attributes."):
                    attributes[key.removeprefix("attributes.")] = coerce_value(value)
                elif key.startswith("metadata."):
                    metadata[key.removeprefix("metadata.")] = value
                elif key == "certifications":
                    product[key] = [item.strip() for item in str(value).split("|") if item.strip()]
                else:
                    product[key] = value
            product["attributes"] = attributes
            product["metadata"] = metadata
            products.append(product)
        return products
    payload = json.loads(text)
    if isinstance(payload, dict):
        payload = payload.get("products")
    if not isinstance(payload, list):
        raise ValueError("import payload must be a JSON product array or CSV")
    return payload


def coerce_value(value: Any) -> Any:
    if value in ("", None):
        return value
    try:
        if "." in str(value):
            return float(value)
        return int(value)
    except ValueError:
        return value


def products_csv(products: list[dict[str, Any]]) -> bytes:
    fields = [
        "id",
        "sku",
        "name",
        "family",
        "lifecycle_status",
        "certifications",
        "metadata.certification_status",
        "metadata.classification",
        "metadata.owner",
        "attributes.gtin",
        "attributes.co2_kg",
        "attributes.recyclable_share_pct",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for product in products:
        row = {}
        for field in fields:
            value = nested_value(product, field)
            if isinstance(value, list):
                value = "|".join(str(item) for item in value)
            row[field] = value
        writer.writerow(row)
    return buffer.getvalue().encode("utf-8")


def nested_value(payload: dict[str, Any], dotted: str) -> Any:
    current: Any = payload
    for part in dotted.split("."):
        if not isinstance(current, dict):
            return ""
        current = current.get(part, "")
    return current


def render_docs(host: str) -> str:
    spec = html.escape(json.dumps(openapi_spec(host), indent=2))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Thebenpaul Product Layer API Docs</title>
  <link rel="stylesheet" href="/styles.css">
</head>
<body class="docs">
  <main>
    <h1>Thebenpaul Product Layer API</h1>
    <p>Local OpenAPI documentation. Use <code>X-Role: viewer|editor|steward|admin</code> to exercise RBAC/ABAC behavior.</p>
    <p><a href="/api/openapi.json">OpenAPI JSON</a> | <a href="/">Web UI</a></p>
    <pre>{spec}</pre>
  </main>
</body>
</html>"""


def passport_html(product: dict[str, Any]) -> str:
    p = passport(product)
    rows = "".join(
        f"<tr><th>{html.escape(str(key))}</th><td>{html.escape(str(value))}</td></tr>"
        for key, value in sorted(p["attributes"].items())
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>DPP {html.escape(str(p["product"]["sku"]))}</title>
  <link rel="stylesheet" href="/styles.css">
</head>
<body class="print">
  <main>
    <h1>Digital Product Passport</h1>
    <section>
      <h2>{html.escape(str(p["product"]["name"]))}</h2>
      <p><strong>SKU:</strong> {html.escape(str(p["product"]["sku"]))}</p>
      <p><strong>Family:</strong> {html.escape(str(p["product"]["family"]))}</p>
      <p><strong>Certifications:</strong> {html.escape(", ".join(p["compliance"]["certifications"]))}</p>
      <p><strong>Lineage:</strong> {html.escape(str(p["identity"]["lineage"]))}</p>
    </section>
    <section>
      <h2>Attributes</h2>
      <table>{rows}</table>
    </section>
    <footer>Generated {html.escape(utc_now())}. Print this page to PDF for a local PDF-friendly export.</footer>
  </main>
</body>
</html>"""


def passport_svg(product: dict[str, Any]) -> str:
    p = passport(product)
    name = html.escape(str(p["product"]["name"]))
    sku = html.escape(str(p["product"]["sku"]))
    family = html.escape(str(p["product"]["family"]))
    status = html.escape(str(p["compliance"]["certification_status"]))
    certs = html.escape(", ".join(p["compliance"]["certifications"]))
    co2 = html.escape(str(p["sustainability"]["co2_kg"]))
    rec = html.escape(str(p["sustainability"]["recyclable_share_pct"]))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" viewBox="0 0 960 540" role="img">
  <rect width="960" height="540" fill="#f7f8f5"/>
  <rect x="42" y="42" width="876" height="456" rx="8" fill="#ffffff" stroke="#2e3a34" stroke-width="2"/>
  <rect x="42" y="42" width="876" height="92" fill="#16382e"/>
  <text x="72" y="98" fill="#ffffff" font-family="Arial, sans-serif" font-size="32" font-weight="700">Digital Product Passport</text>
  <text x="72" y="176" fill="#1d2a25" font-family="Arial, sans-serif" font-size="30" font-weight="700">{name}</text>
  <text x="72" y="220" fill="#42534b" font-family="Arial, sans-serif" font-size="22">SKU {sku} | {family}</text>
  <text x="72" y="282" fill="#1d2a25" font-family="Arial, sans-serif" font-size="24">Compliance</text>
  <text x="72" y="320" fill="#42534b" font-family="Arial, sans-serif" font-size="20">Status: {status}</text>
  <text x="72" y="352" fill="#42534b" font-family="Arial, sans-serif" font-size="20">Certificates: {certs}</text>
  <text x="560" y="282" fill="#1d2a25" font-family="Arial, sans-serif" font-size="24">Sustainability</text>
  <text x="560" y="320" fill="#42534b" font-family="Arial, sans-serif" font-size="20">CO2: {co2} kg</text>
  <text x="560" y="352" fill="#42534b" font-family="Arial, sans-serif" font-size="20">Recyclable share: {rec}%</text>
  <text x="72" y="454" fill="#6c7771" font-family="Arial, sans-serif" font-size="16">Thebenpaul product-layer MVP export</text>
</svg>"""


def not_found_html(message: str) -> str:
    return f"<!doctype html><title>Not found</title><h1>{html.escape(message)}</h1>"


def not_found_svg(message: str) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="600" height="120"><text x="20" y="60">{html.escape(message)}</text></svg>'


def make_server(host: str, port: int, store_path: Path = STORE_PATH) -> ThreadingHTTPServer:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((host, port), Handler)
    server.store = ProductStore(store_path)  # type: ignore[attr-defined]
    return server


def local_ip_hint() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Thebenpaul product-layer MVP")
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8080")))
    args = parser.parse_args(argv)
    server = make_server(args.host, args.port)
    print(f"Product-layer running on http://127.0.0.1:{args.port}")
    print(f"LAN hint: http://{local_ip_hint()}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping product-layer")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
