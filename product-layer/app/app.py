#!/usr/bin/env python3
"""Stdlib REST API and static UI server for the Thebenpaul product layer."""

from __future__ import annotations

import argparse
import csv
import html
import io
import json
import logging
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
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("product-layer")


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

IDENTITY_STRING_ATTRIBUTES = {
    "gtin",
    "batch_lot_number",
    "batch_number",
    "lot_number",
    "serial_number",
}

DPP_VIEW_RANK = {"consumer": 0, "b2b": 1, "authority": 2}
DPP_ACCESS_RANK = {"public": 0, "b2b": 1, "authority": 2}
DPP_GRANULARITY_LEVELS = ["model", "batch", "item"]
DPP_UPDATE_METADATA_KEYS = {
    "change_rationale",
    "data_matrix_contrast",
    "data_matrix_durability",
    "data_matrix_placement",
    "data_matrix_target_grade",
    "dpp_granularity",
    "dpp_status",
    "dpp_version",
    "manufacturer_address",
    "manufacturer_name",
    "region",
    "valid_from",
    "valid_until",
    "useful_life_commitment",
}

DPP_FIELD_DEFINITIONS = [
    {
        "key": "product_name",
        "label": "Product name",
        "source": "name",
        "classification": "Essential",
        "granularity": "model",
        "access": "public",
        "data_type": "string",
    },
    {
        "key": "model",
        "label": "Model or SKU",
        "source": "sku",
        "classification": "Essential",
        "granularity": "model",
        "access": "public",
        "data_type": "string",
    },
    {
        "key": "product_family",
        "label": "Product family",
        "source": "family",
        "classification": "Essential",
        "granularity": "model",
        "access": "public",
        "data_type": "string",
    },
    {
        "key": "gtin",
        "label": "GTIN",
        "source": "attributes.gtin",
        "classification": "Essential",
        "granularity": "model",
        "access": "public",
        "data_type": "string",
    },
    {
        "key": "batch_lot_number",
        "label": "Batch or lot number",
        "source": "attributes.batch_lot_number",
        "classification": "Strongly Recommended",
        "granularity": "batch",
        "access": "public",
        "data_type": "string",
    },
    {
        "key": "serial_number",
        "label": "Serial number",
        "source": "attributes.serial_number",
        "classification": "Strongly Recommended",
        "granularity": "item",
        "access": "public",
        "data_type": "string",
    },
    {
        "key": "public_dpp_url",
        "label": "Public DPP URL",
        "source": "dpp.public_url",
        "classification": "Essential",
        "granularity": "item",
        "access": "public",
        "data_type": "uri",
    },
    {
        "key": "manufacturer_name",
        "label": "Manufacturer",
        "source": "metadata.manufacturer_name",
        "classification": "Essential",
        "granularity": "model",
        "access": "public",
        "data_type": "string",
        "fallback": "Thebenpaul GmbH",
    },
    {
        "key": "manufacturer_address",
        "label": "Manufacturer address",
        "source": "metadata.manufacturer_address",
        "classification": "Essential",
        "granularity": "model",
        "access": "public",
        "data_type": "string",
        "fallback": "Hoefener Strasse 52, 72622 Nuertingen, Germany",
    },
    {
        "key": "production_region",
        "label": "Country or region of production",
        "source": "metadata.region",
        "classification": "Strongly Recommended",
        "granularity": "batch",
        "access": "public",
        "data_type": "string",
    },
    {
        "key": "main_materials",
        "label": "Main materials",
        "source": "attributes.main_materials",
        "classification": "Essential",
        "granularity": "model",
        "access": "public",
        "data_type": "string",
    },
    {
        "key": "recycled_content_share_pct",
        "label": "Recycled content share",
        "source": "attributes.recycled_content_share_pct",
        "classification": "Strongly Recommended",
        "granularity": "model",
        "access": "public",
        "data_type": "number",
        "unit": "%",
    },
    {
        "key": "recyclable_share_pct",
        "label": "Recyclable share",
        "source": "attributes.recyclable_share_pct",
        "classification": "Strongly Recommended",
        "granularity": "model",
        "access": "public",
        "data_type": "number",
        "unit": "%",
    },
    {
        "key": "substances_of_concern",
        "label": "Substances of concern",
        "source": "attributes.substances_of_concern",
        "classification": "Essential",
        "granularity": "model",
        "access": "public",
        "data_type": "string",
        "fallback": "None declared above configured regulatory thresholds",
    },
    {
        "key": "repairability_information",
        "label": "Repairability information",
        "source": "attributes.repairability_information",
        "classification": "Strongly Recommended",
        "granularity": "model",
        "access": "public",
        "data_type": "string",
        "fallback": "Service and repair information is available through the Thebenpaul service channel.",
    },
    {
        "key": "spare_parts_availability",
        "label": "Spare parts availability",
        "source": "attributes.spare_parts_availability",
        "classification": "Strongly Recommended",
        "granularity": "model",
        "access": "public",
        "data_type": "string",
        "fallback": "Available during the declared useful life of the product.",
    },
    {
        "key": "disassembly_recycling_instructions",
        "label": "Disassembly and recycling instructions",
        "source": "attributes.disassembly_recycling_instructions",
        "classification": "Essential",
        "granularity": "model",
        "access": "public",
        "data_type": "string",
        "fallback": "Separate electronic components and housing materials; route through certified WEEE recycling.",
    },
    {
        "key": "carbon_footprint_kg",
        "label": "Carbon footprint",
        "source": "attributes.co2_kg",
        "classification": "Voluntary",
        "granularity": "model",
        "access": "public",
        "data_type": "number",
        "unit": "kg CO2e",
    },
    {
        "key": "certifications",
        "label": "EU declarations and standards",
        "source": "certifications",
        "classification": "Essential",
        "granularity": "model",
        "access": "public",
        "data_type": "list",
    },
    {
        "key": "documents",
        "label": "Documentation references",
        "source": "documents",
        "classification": "Strongly Recommended",
        "granularity": "model",
        "access": "public",
        "data_type": "list",
    },
    {
        "key": "commercial_price_eur",
        "label": "Commercial price",
        "source": "attributes.commercial_price_eur",
        "classification": "Voluntary",
        "granularity": "model",
        "access": "b2b",
        "data_type": "number",
        "unit": "EUR",
    },
    {
        "key": "source_system",
        "label": "Source system",
        "source": "metadata.source_system",
        "classification": "Strongly Recommended",
        "granularity": "model",
        "access": "b2b",
        "data_type": "string",
    },
    {
        "key": "lineage",
        "label": "Lineage",
        "source": "metadata.lineage",
        "classification": "Strongly Recommended",
        "granularity": "model",
        "access": "authority",
        "data_type": "string",
    },
    {
        "key": "quality_status",
        "label": "Quality status",
        "source": "quality.status",
        "classification": "Essential",
        "granularity": "model",
        "access": "authority",
        "data_type": "string",
    },
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
        self.sync_state: dict[str, Any] = {}
        self.audit_events: list[dict[str, Any]] = []
        self._last_mtime_ns: int | None = None
        self.auto_reload = os.environ.get("THEBEN_STORE_AUTO_RELOAD", "true").strip().lower() not in ("0", "false", "no", "off")
        self.load()

    def _store_mtime_ns(self) -> int | None:
        try:
            return self.path.stat().st_mtime_ns
        except OSError:
            return None

    def _track_store_mtime(self) -> None:
        self._last_mtime_ns = self._store_mtime_ns()

    def reload_if_changed(self) -> bool:
        if not self.auto_reload:
            return False
        with self.lock:
            current = self._store_mtime_ns()
            if current is None or self._last_mtime_ns is None or current == self._last_mtime_ns:
                return False
            self.load()
            return True

    def load(self) -> None:
        with self.lock:
            payload = load_json(self.path, None)
            if not payload:
                self.products = generate_products(1000)
                self.sync_state = default_sync_state("mock-generator")
                self.save()
            elif isinstance(payload, dict):
                self.products = payload.get("products", [])
                self.sync_state = payload.get("sync_state") or default_sync_state("file-store")
                self.audit_events = payload.get("audit_events") or []
            elif isinstance(payload, list):
                self.products = payload
                self.sync_state = default_sync_state("legacy-list-store")
                self.audit_events = []
            else:
                self.products = []
                self.sync_state = default_sync_state("invalid-store")
                self.audit_events = []
            self._track_store_mtime()

    def save(self) -> None:
        with self.lock:
            save_json(
                self.path,
                {
                    "schema_version": "1.0.0",
                    "generated_at": utc_now(),
                    "sync_state": self.sync_state,
                    "audit_events": self.audit_events[-200:],
                    "products": self.products,
                },
            )
            self._track_store_mtime()

    def list_products(self, query: dict[str, list[str]], user: dict[str, Any]) -> list[dict[str, Any]]:
        self.reload_if_changed()
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
        self.reload_if_changed()
        with self.lock:
            for product in self.products:
                if product.get("id") == product_id:
                    if not row_allowed(product, user):
                        return None
                    return apply_access_controls(product, user)
        return None

    def get_raw_product(self, product_id: str) -> dict[str, Any] | None:
        self.reload_if_changed()
        with self.lock:
            for product in self.products:
                if product.get("id") == product_id:
                    return json.loads(json.dumps(product))
        return None

    def upsert_product(self, incoming: dict[str, Any]) -> dict[str, Any]:
        product = normalize_product(incoming)
        with self.lock:
            self.reload_if_changed()
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
            self.reload_if_changed()
            for product in self.products:
                if product.get("id") == product_id:
                    product.setdefault("attributes", {}).update(attributes)
                    product["updated_at"] = utc_now()
                    self.save()
                    return product
        return None

    def update_dpp_record(self, product_id: str, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any] | None:
        attributes = payload.get("attributes") or {}
        metadata_updates = payload.get("metadata") or {}
        if not isinstance(attributes, dict):
            raise ValueError("attributes object required")
        if not isinstance(metadata_updates, dict):
            raise ValueError("metadata object required")
        for key in DPP_UPDATE_METADATA_KEYS:
            if key in payload:
                metadata_updates[key] = payload[key]
        if not attributes and not metadata_updates and "change_rationale" not in payload:
            raise ValueError("attributes, metadata, dpp_version, or change_rationale required")

        with self.lock:
            self.reload_if_changed()
            for product in self.products:
                if product.get("id") != product_id:
                    continue
                metadata = product.setdefault("metadata", {})
                previous_version = str(metadata.get("dpp_version") or metadata.get("contract_version") or "0.1.0")
                rationale = str(
                    metadata_updates.get("change_rationale")
                    or payload.get("change_rationale")
                    or "DPP metadata update via product-layer API."
                ).strip()
                next_version = str(metadata_updates.get("dpp_version") or bump_dpp_version(previous_version)).strip()

                product.setdefault("attributes", {}).update(attributes)
                metadata.update(metadata_updates)
                metadata["dpp_version"] = next_version
                metadata["change_rationale"] = rationale
                history = metadata.setdefault("dpp_version_history", [])
                if not isinstance(history, list):
                    history = []
                    metadata["dpp_version_history"] = history
                history.append(
                    {
                        "version": next_version,
                        "previous_version": previous_version,
                        "changed_at": utc_now(),
                        "change_rationale": rationale,
                        "changed_by_role": user.get("role", "viewer"),
                    }
                )
                product["updated_at"] = utc_now()
                self.save()
                return json.loads(json.dumps(product))
        return None

    def import_products(self, products: list[dict[str, Any]], source: dict[str, Any] | None = None) -> dict[str, Any]:
        self.reload_if_changed()
        imported = []
        errors = []
        for index, product in enumerate(products):
            try:
                imported.append(self.upsert_product(product))
            except ValueError as exc:
                logger.error("IMPORT row %d FAILED: %s (product data: %s)",
                             index + 1, exc, {k: product.get(k) for k in ("id", "sku", "name")})
                errors.append({"row": index + 1, "error": str(exc)})
        if source is not None:
            self.sync_state = {
                "last_sync_at": utc_now(),
                "source": source,
                "received": len(products),
                "imported": len(imported),
                "errors": errors,
            }
            self.save()
        return {"imported": len(imported), "errors": errors, "products": imported[:20]}

    def record_audit(
        self,
        *,
        action: str,
        product_id: str,
        role: str,
        view: str,
        channel: str,
        outcome: str = "success",
        details: dict[str, Any] | None = None,
        actor: str | None = None,
    ) -> dict[str, Any]:
        event = {
            "event_id": f"audit-{int(time.time() * 1000)}-{len(self.audit_events) + 1}",
            "occurred_at": utc_now(),
            "action": action,
            "product_id": product_id,
            "role": role,
            "actor": actor or f"local-{role}",
            "dpp_view": view,
            "channel": channel,
            "outcome": outcome,
        }
        if details:
            event["details"] = details
        with self.lock:
            self.reload_if_changed()
            self.audit_events.append(event)
            self.audit_events = self.audit_events[-200:]
            self.save()
        return event

    def audit_for_product(self, product_id: str, limit: int = 20) -> list[dict[str, Any]]:
        self.reload_if_changed()
        with self.lock:
            events = [event for event in self.audit_events if event.get("product_id") == product_id]
        return events[-limit:]


def default_sync_state(source_name: str) -> dict[str, Any]:
    return {
        "last_sync_at": None,
        "source": {"type": source_name},
        "received": 0,
        "imported": 0,
        "errors": [],
    }


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
        "gtin": f"04003468{idx:06d}",
        "batch_lot_number": f"LOT-2026-{((idx - 1) // 100) + 1:03d}",
        "serial_number": f"SN-{idx:010d}",
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


def product_identity(product: dict[str, Any]) -> dict[str, Any]:
    attrs = product.get("attributes", {})
    gtin = str(attrs.get("gtin") or "").strip()
    batch_lot_number = str(
        attrs.get("batch_lot_number") or attrs.get("batch_number") or attrs.get("lot_number") or ""
    ).strip()
    serial_number = str(attrs.get("serial_number") or "").strip()
    gtin_14 = gtin.zfill(14) if gtin.isdigit() and len(gtin) <= 14 else gtin
    data_matrix_payload = ""
    if gtin_14 and batch_lot_number and serial_number:
        data_matrix_payload = f"(01){gtin_14}(10){batch_lot_number}(21){serial_number}"
    return {
        "gtin": gtin,
        "gtin_14": gtin_14,
        "batch_lot_number": batch_lot_number,
        "serial_number": serial_number,
        "globally_unique_instance_id": f"{gtin_14}:{serial_number}" if gtin_14 and serial_number else "",
        "data_matrix": {
            "symbology": "GS1 DataMatrix",
            "payload": data_matrix_payload,
            "application_identifiers": {
                "01": "GTIN",
                "10": "Batch or lot number",
                "21": "Serial number",
            },
        },
        "rules": [
            "GTIN identifies the trade item.",
            "All identical trade items from the same source carry the same GTIN.",
            "Batch or lot number identifies a production batch sharing the same GTIN.",
            "Serial number identifies one individual product instance.",
            "GTIN plus serial number is globally unique for a product instance.",
        ],
    }


def dpp_field_catalog() -> dict[str, Any]:
    tiers = ["Essential", "Strongly Recommended", "Voluntary"]
    return {
        "methodology": "JRC three-tier DPP field classification",
        "tiers": tiers,
        "granularity_levels": DPP_GRANULARITY_LEVELS,
        "field_count": len(DPP_FIELD_DEFINITIONS),
        "fields": DPP_FIELD_DEFINITIONS,
    }


def normalized_dpp_view(view: str | None) -> str:
    candidate = str(view or "consumer").strip().lower()
    return candidate if candidate in DPP_VIEW_RANK else "consumer"


def requested_dpp_view(query: dict[str, list[str]]) -> str:
    values = query.get("view") or query.get("role") or ["consumer"]
    return normalized_dpp_view(values[0])


def dpp_view_allowed(user: dict[str, Any], view: str) -> bool:
    view = normalized_dpp_view(view)
    if view == "consumer":
        return True
    if view == "b2b":
        return has_permission(user, "product:write") or has_permission(user, "product:import")
    return has_permission(user, "product:read_all_regions")


def bump_dpp_version(version: str) -> str:
    parts = str(version or "0.1.0").split(".")
    if not parts or any(not part.isdigit() for part in parts):
        return f"{version}.1"
    while len(parts) < 3:
        parts.append("0")
    parts[-1] = str(int(parts[-1]) + 1)
    return ".".join(parts)


def dpp_public_base_url(host: str) -> str:
    configured = os.environ.get("THEBEN_PUBLIC_BASE_URL", "").strip()
    runtime_public = str(RUNTIME_CONFIG.get("service", {}).get("public_base_url") or "").strip()
    if configured:
        return configured.rstrip("/")
    if runtime_public:
        return runtime_public.rstrip("/")
    host = (host or "localhost").strip()
    if host.startswith(("http://", "https://")):
        return host.rstrip("/")
    return f"http://{host}".rstrip("/")


def dpp_public_url(product: dict[str, Any], public_base_url: str) -> str:
    return f"{public_base_url.rstrip('/')}/dpp/{product.get('id')}"


def dpp_granularity(product: dict[str, Any]) -> dict[str, Any]:
    metadata = product.get("metadata", {})
    identity = product_identity(product)
    declared = str(metadata.get("dpp_granularity") or "").strip().lower()
    if declared not in DPP_GRANULARITY_LEVELS:
        if identity.get("serial_number"):
            declared = "item"
        elif identity.get("batch_lot_number"):
            declared = "batch"
        else:
            declared = "model"
    return {
        "declared_level": declared,
        "supported_levels": DPP_GRANULARITY_LEVELS,
        "model_identifier": product.get("sku"),
        "batch_identifier": identity.get("batch_lot_number"),
        "item_identifier": identity.get("serial_number"),
    }


def dpp_data_matrix_record(product: dict[str, Any], public_url: str) -> dict[str, Any]:
    identity = product_identity(product)
    return {
        "carrier_type": "Data Matrix",
        "symbology": "Data Matrix ECC 200 / GS1 DataMatrix compatible",
        "encoded_content": public_url,
        "public_url": public_url,
        "gs1_payload": identity["data_matrix"]["payload"],
        "placement": product.get("metadata", {}).get("data_matrix_placement", "product label"),
        "print_quality": {
            "target_grade": product.get("metadata", {}).get("data_matrix_target_grade", "B or better"),
            "contrast": product.get("metadata", {}).get("data_matrix_contrast", "high contrast"),
            "durability": product.get("metadata", {}).get("data_matrix_durability", "readable for product useful life"),
        },
        "machine_readable": bool(public_url),
        "human_label": "Digital Product Passport",
    }


def family_materials(family: str) -> str:
    materials = {
        "Time Switch": "PC/ABS housing, copper contacts, printed circuit board, electronic components",
        "Motion Detector": "PC housing, lens polymer, printed circuit board, electronic components",
        "HVAC Controller": "PC/ABS housing, copper conductors, display components, printed circuit board",
        "KNX Actuator": "PC/ABS housing, copper conductors, relay contacts, printed circuit board",
        "Energy Meter": "PC housing, copper conductors, measuring transformer, printed circuit board",
    }
    return materials.get(family, "Housing polymer, copper conductors, printed circuit board, electronic components")


def dpp_context_value(product: dict[str, Any], source: str, public_url: str) -> Any:
    if source == "dpp.public_url":
        return public_url
    if source == "attributes.main_materials":
        value = nested_value(product, source)
        return value or family_materials(str(product.get("family") or ""))
    value = nested_value(product, source)
    return value


def dpp_fields(product: dict[str, Any], view: str, public_url: str) -> list[dict[str, Any]]:
    rank = DPP_VIEW_RANK[normalized_dpp_view(view)]
    fields = []
    for definition in DPP_FIELD_DEFINITIONS:
        if DPP_ACCESS_RANK[definition["access"]] > rank:
            continue
        value = dpp_context_value(product, definition["source"], public_url)
        if value in ("", None, [], {}):
            value = definition.get("fallback")
        fields.append(
            {
                "id": definition["key"],
                "key": definition["key"],
                "label": definition["label"],
                "value": value,
                "tier": definition["classification"].lower().replace(" ", "_"),
                "classification": definition["classification"],
                "granularity": definition["granularity"],
                "access": definition["access"],
                "data_type": definition["data_type"],
                "unit": definition.get("unit"),
                "status": "available" if value not in ("", None, [], {}) else "missing",
            }
        )
    return fields


def dpp_lifecycle(product: dict[str, Any]) -> dict[str, Any]:
    metadata = product.get("metadata", {})
    product_state = product.get("lifecycle_status", "active")
    status = metadata.get("dpp_status")
    if not status:
        status = "withdrawn" if product_state in ("retired", "withdrawn") else "active"
    version = str(metadata.get("dpp_version") or metadata.get("contract_version") or "0.1.0")
    version_history = metadata.get("dpp_version_history")
    if not isinstance(version_history, list) or not version_history:
        version_history = [
            {
                "version": version,
                "changed_at": product.get("updated_at"),
                "change_rationale": metadata.get("change_rationale", "Current curated product-layer DPP projection."),
            }
        ]
    return {
        "dpp_status": status,
        "product_lifecycle_status": product_state,
        "version": version,
        "created_at": product.get("created_at"),
        "updated_at": product.get("updated_at"),
        "valid_from": metadata.get("valid_from") or product.get("created_at"),
        "valid_until": metadata.get("valid_until"),
        "useful_life_commitment": metadata.get(
            "useful_life_commitment",
            "Public DPP URL remains stable for the useful life of the product and beyond for repair and recycling.",
        ),
        "version_history": version_history,
    }


def dpp_record(
    product: dict[str, Any],
    view: str = "consumer",
    public_base_url: str = "http://localhost",
    audit_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    view = normalized_dpp_view(view)
    identity = product_identity(product)
    public_base_url = dpp_public_base_url(public_base_url)
    public_url = dpp_public_url(product, public_base_url)
    fields = dpp_fields(product, view, public_url)
    lifecycle = dpp_lifecycle(product)
    data_carrier = dpp_data_matrix_record(product, public_url)
    return {
        "dpp_id": f"dpp-{product.get('id')}",
        "record_type": "eu_digital_product_passport",
        "schema_version": "0.2.0",
        "record_version": lifecycle["version"],
        "view": view,
        "status": lifecycle["dpp_status"],
        "public_url": public_url,
        "languages": DPP_CONFIG.get("default_languages", ["en", "de"]),
        "regulatory_context": DPP_CONFIG.get("regulatory_context", {}),
        "standards_alignment": {
            "regulatory_context": ["ESPR", "JRC DPP data requirement methodology", "CEN/CENELEC JTC 24-ready"],
            "field_classification": dpp_field_catalog(),
            "data_carrier": "Data Matrix code encodes a stable public DPP URL.",
        },
        "granularity": dpp_granularity(product),
        "lifecycle": lifecycle,
        "identifiers": {
            "internal_product_id": product.get("id"),
            "sku": product.get("sku"),
            "gtin": identity.get("gtin"),
            "gtin_14": identity.get("gtin_14"),
            "batch_lot_number": identity.get("batch_lot_number"),
            "serial_number": identity.get("serial_number"),
            "globally_unique_instance_id": identity.get("globally_unique_instance_id"),
        },
        "identity": identity,
        "data_carrier": data_carrier,
        "data_matrix": {
            **identity["data_matrix"],
            "encoded_content": data_carrier["encoded_content"],
            "structured_identifier": data_carrier["gs1_payload"],
            "public_url": data_carrier["public_url"],
            "print_quality": data_carrier["print_quality"],
        },
        "fields": fields,
        "quality": {
            "essential_missing": [
                field["key"] for field in fields if field["classification"] == "Essential" and field["status"] == "missing"
            ],
            "strongly_recommended_missing": [
                field["key"]
                for field in fields
                if field["classification"] == "Strongly Recommended" and field["status"] == "missing"
            ],
            "product_quality": product.get("quality", {}),
        },
        "audit": {
            "surface": "lightweight product-layer audit ring buffer",
            "events": audit_events or [],
        },
        "generated_at": utc_now(),
    }


def dpp_versions(product: dict[str, Any]) -> dict[str, Any]:
    lifecycle = dpp_lifecycle(product)
    versions = [{**entry, "status": lifecycle["dpp_status"]} for entry in lifecycle["version_history"]]
    return {
        "dpp_id": f"dpp-{product.get('id')}",
        "current_version": lifecycle["version"],
        "status": lifecycle["dpp_status"],
        "versions": versions,
        "lifecycle": lifecycle,
    }


def dpp_audit(product: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "dpp_id": f"dpp-{product.get('id')}",
        "product_id": product.get("id"),
        "events": events,
        "retention": "local product-layer ring buffer, capped at 200 events for the MVP",
    }


def json_for_script(payload: Any) -> str:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    return text.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


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
METADATA_CONFIG = load_json(CONFIG_DIR / "metadata_schema.json", {})
RUNTIME_CONFIG = load_json(CONFIG_DIR / "runtime.json", {})
DPP_CONFIG = load_json(CONFIG_DIR / "dpp_schema.json", {})


def bool_from_env(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def data_layer_sync_config() -> dict[str, Any]:
    configured = dict(RUNTIME_CONFIG.get("data_layer_sync") or {})
    source_url = os.environ.get("THEBEN_DATA_LAYER_EXPORT_URL") or configured.get("source_url", "")
    timeout_raw = (
        os.environ.get("THEBEN_DATA_LAYER_SYNC_TIMEOUT")
        or os.environ.get("THEBEN_DATA_LAYER_TIMEOUT")
        or configured.get("timeout_seconds", 5)
    )
    try:
        timeout_seconds = float(timeout_raw)
    except (TypeError, ValueError):
        timeout_seconds = 5.0
    allowed_hosts = os.environ.get("THEBEN_DATA_LAYER_ALLOWED_HOSTS")
    if allowed_hosts:
        hosts = [host.strip().lower() for host in allowed_hosts.split(",") if host.strip()]
    else:
        hosts = list(configured.get("allowed_hosts") or ["127.0.0.1", "localhost", "host.docker.internal", "backend"])
    return {
        "enabled": bool_from_env(os.environ.get("THEBEN_DATA_LAYER_SYNC_ENABLED"), bool(configured.get("enabled", True))),
        "source_url": source_url,
        "timeout_seconds": max(0.5, min(timeout_seconds, 60.0)),
        "contract": configured.get("contract", "product-layer-products-json-v1"),
        "mode": configured.get("mode", "pull"),
        "allowed_hosts": hosts,
    }


def sync_from_data_layer(store: ProductStore, config: dict[str, Any] | None = None) -> dict[str, Any]:
    effective = config or data_layer_sync_config()
    if not effective.get("enabled"):
        raise ValueError("data-layer sync is disabled")
    source_url = str(effective.get("source_url") or "").strip()
    if not source_url:
        raise ValueError("data-layer sync source_url is not configured")
    logger.info("SYNC: starting from %s", source_url)
    validate_data_layer_url(source_url, effective.get("allowed_hosts") or [])
    payload = fetch_data_layer_export(source_url, float(effective.get("timeout_seconds", 5)))
    product_count = len(payload.get("products", []))
    logger.info("SYNC: fetched %d products from data-layer (schema %s, generated %s)",
                product_count, payload.get("schema_version"), payload.get("generated_at"))
    products = prepare_data_layer_products(payload, source_url)
    source = {
        "type": "data-layer-export",
        "url": source_url,
        "contract": effective.get("contract"),
        "schema_version": payload.get("schema_version"),
        "generated_at": payload.get("generated_at"),
        "lakehouse_layer": "curated",
        "domain_module": "product",
    }
    result = store.import_products(products, source)
    imported_count = result.get("imported", 0)
    error_count = len(result.get("errors", []))
    if error_count:
        logger.warning("SYNC DONE: %d imported, %d ERRORS: %s",
                       imported_count, error_count, result["errors"])
    else:
        logger.info("SYNC DONE: %d/%d products imported successfully", imported_count, product_count)
    result["source"] = source
    result["sync_state"] = store.sync_state
    return result


def current_user(headers: Any) -> dict[str, Any]:
    default_role = os.environ.get("THEBEN_DEFAULT_ROLE", "viewer")
    requested_role = headers.get("X-Role") or default_role
    role_token = os.environ.get("THEBEN_ROLE_TOKEN", "").strip()
    provided_token = (headers.get("X-Role-Token") or "").strip()
    auth_header = (headers.get("Authorization") or "").strip()
    if auth_header.lower().startswith("bearer "):
        provided_token = auth_header[7:].strip()
    role = requested_role
    if role_token and provided_token != role_token:
        role = default_role
    actor = headers.get("X-User") or headers.get("X-Actor") or headers.get("X-Email") or f"local-{role}"
    purpose = headers.get("X-Purpose") or "analytics"
    region = headers.get("X-Region") or "EU"
    return {"role": role, "purpose": purpose, "region": region, "actor": actor}


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

    identity = product_identity(product)
    gtin = identity["gtin"]
    if gtin and (not gtin.isdigit() or len(gtin) not in (8, 12, 13, 14)):
        issues.append({"severity": "error", "field": "attributes.gtin", "message": "GTIN must be 8, 12, 13, or 14 digits"})
    if identity["serial_number"] and not identity["gtin"]:
        issues.append({"severity": "error", "field": "attributes.serial_number", "message": "serial number requires GTIN"})
    if identity["data_matrix"]["payload"] and not identity["globally_unique_instance_id"]:
        issues.append({"severity": "error", "field": "attributes.serial_number", "message": "GTIN and serial number must identify one product instance"})

    dpp_quality = dpp_record(product, "consumer", "http://localhost")["quality"]
    for key in dpp_quality["essential_missing"]:
        issues.append({"severity": "error", "field": f"dpp.{key}", "message": "essential DPP field missing"})
    for key in dpp_quality["strongly_recommended_missing"]:
        issues.append({"severity": "warning", "field": f"dpp.{key}", "message": "strongly recommended DPP field missing"})

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


def data_layer_contract() -> dict[str, Any]:
    runtime_contract = RUNTIME_CONFIG.get("data_layer_contract", {})
    sync_config = data_layer_sync_config()
    env_url = os.environ.get("THEBEN_DATA_LAYER_EXPORT_URL", "").strip()
    configured_url = sync_config.get("source_url") or runtime_contract.get("export_url", "")
    export_url = env_url or configured_url or "http://host.docker.internal:8000/api/v1/export/products.json"
    return {
        **runtime_contract,
        "status": "active_adapter",
        "sync_enabled": bool(sync_config.get("enabled")),
        "export_url": export_url,
        "timeout_seconds": sync_config.get("timeout_seconds"),
        "mode": sync_config.get("mode"),
        "contract": sync_config.get("contract"),
        "source_layer": "standardized",
        "target_layer": "curated",
        "source_endpoint": "/api/v1/export/products.json",
        "target_data_product": METADATA_CONFIG.get("data_product", {}).get("target_table", "curated_product.product_master_dpp"),
        "interface_version": METADATA_CONFIG.get("data_product", {}).get("contract_version", "0.1.0"),
        "sync_permission": "product:import",
    }


def catalog_data_products() -> dict[str, Any]:
    product = METADATA_CONFIG.get("data_product", {})
    return {
        "data_products": [
            {
                **product,
                "definition": "Domain-owned, documented, versioned, and quality-tested data asset.",
                "layer": "curated",
                "module": "product",
                "mandatory_metadata": METADATA_CONFIG.get("mandatory_metadata", []),
                "approved_consumption_channels": [
                    "BI",
                    "analytics",
                    "operational apps",
                    "REST APIs",
                    "controlled external sharing",
                ],
                "interfaces": {
                    "rest": ["/api/products", "/api/passport/{id}", "/api/export/products.csv"],
                    "dpp": ["/api/dpp/{id}", "/dpp/{id}", "/api/dpp/field-catalog"],
                    "upstream": data_layer_contract().get("source_endpoint"),
                    "target_lakehouse": {
                        "format": product.get("target_lakehouse_table_format", "Apache Iceberg"),
                        "table": product.get("target_table", "curated_product.product_master_dpp"),
                    },
                },
            }
        ],
        "generated_at": utc_now(),
    }


def lineage_model() -> dict[str, Any]:
    return {
        "architecture": "central lakehouse backbone with decentralized domain modules",
        "layers": [
            {
                "name": "raw",
                "owner": "central_it",
                "description": "Source-aligned ingestion for CSV, JSON, XML, XLSX, PDF, REST, and future IoT feeds.",
                "access": ACCESS_CONFIG.get("layer_access", {}).get("raw", []),
            },
            {
                "name": "standardized",
                "owner": "central_it_and_data_layer",
                "description": "Normalized records and document references exposed by the PAUL data-layer.",
                "interface": data_layer_contract().get("source_endpoint"),
                "access": ACCESS_CONFIG.get("layer_access", {}).get("standardized", []),
            },
            {
                "name": "curated",
                "owner": "product_domain",
                "description": "Business-certified product data products for DPP, analytics, and service use cases.",
                "table_format": "Apache Iceberg",
                "target_table": METADATA_CONFIG.get("data_product", {}).get("target_table"),
                "access": ACCESS_CONFIG.get("layer_access", {}).get("curated", []),
            },
            {
                "name": "consumption",
                "owner": "platform_and_domains",
                "description": "Governed REST, BI, analytics, operational app, export, and external sharing interfaces.",
                "access": ACCESS_CONFIG.get("layer_access", {}).get("consumption", []),
            },
        ],
        "current_mvp_lineage": METADATA_CONFIG.get("lineage_contract", {}).get("current_mvp"),
        "target_lineage": METADATA_CONFIG.get("lineage_contract", {}).get("target"),
        "generated_at": utc_now(),
    }


def fetch_data_layer_export(url: str, timeout: float = 10.0) -> dict[str, Any]:
    if not url:
        raise ValueError("data-layer export URL is not configured")
    request = Request(url, headers={"Accept": JSON})
    logger.info("FETCH: GET %s (timeout=%.1fs)", url, timeout)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(20_000_000)
    except HTTPError as exc:
        logger.error("FETCH FAILED: HTTP %d from %s", exc.code, url)
        raise ValueError(f"data-layer export returned HTTP {exc.code}") from exc
    except URLError as exc:
        logger.error("FETCH FAILED: %s unreachable: %s", url, exc.reason)
        raise ValueError(f"data-layer export is unavailable: {exc.reason}") from exc
    logger.info("FETCH: received %d bytes", len(raw))
    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        logger.error("FETCH FAILED: invalid JSON from %s: %s", url, exc)
        raise ValueError(f"data-layer export returned invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("data-layer export must be a JSON object")
    products = payload.get("products")
    if not isinstance(products, list):
        logger.error("FETCH FAILED: no 'products' array in response from %s", url)
        raise ValueError("data-layer export must contain a products array")
    return payload


def validate_data_layer_url(url: str, allowed_hosts: list[str]) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("data-layer export URL must use http or https")
    host = (parsed.hostname or "").lower()
    normalized_allowed = {item.lower() for item in allowed_hosts}
    if normalized_allowed and host not in normalized_allowed:
        raise ValueError(f"data-layer export host is not allowed: {host}")


def prepare_data_layer_products(payload: dict[str, Any], source_url: str) -> list[dict[str, Any]]:
    generated_at = payload.get("generated_at") or utc_now()
    prepared = []
    for product in payload.get("products", []):
        normalized = normalize_product(product)
        metadata = normalized.setdefault("metadata", {})
        metadata["source_system"] = metadata.get("source_system") or "paul-data-layer"
        metadata["lineage"] = metadata.get("lineage") or "paul-ai-ingest -> data-layer-postgres -> product-layer-curated-json"
        metadata["upstream_export_url"] = source_url
        metadata["upstream_export_generated_at"] = generated_at
        metadata["lakehouse_layer"] = "curated"
        metadata["data_product"] = METADATA_CONFIG.get("data_product", {}).get("name", "product-master-dpp")
        metadata["contract_version"] = METADATA_CONFIG.get("data_product", {}).get("contract_version", "0.1.0")
        metadata["target_table"] = METADATA_CONFIG.get("data_product", {}).get("target_table")
        prepared.append(normalized)
    return prepared


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


def data_product_surface(store: ProductStore, user: dict[str, Any]) -> dict[str, Any]:
    sync_config = data_layer_sync_config()
    permissions = role_permissions(user.get("role", "viewer"))
    data_product = METADATA_CONFIG.get("data_product", {})
    return {
        "data_product": data_product,
        "domain_module": {
            "domain": data_product.get("domain", "product"),
            "owner": data_product.get("owner", "Product Data Domain"),
            "steward": data_product.get("steward", "product-data-steward@thebenpaul.local"),
            "curated_table": data_product.get("target_table", "curated_product.product_master_dpp"),
            "table_format": data_product.get("target_lakehouse_table_format", "Apache Iceberg"),
        },
        "lakehouse_layers": {
            "raw": "owned by data-layer ingestion and original document storage",
            "standardized": "normalized PAUL product records and source references",
            "curated": "product-master-dpp domain data product",
            "consumption": "product-layer REST, UI, DPP, CSV, HTML, and SVG exports",
        },
        "interfaces": {
            "sync": "/api/sync/data-layer",
            "products": "/api/products",
            "passport": "/api/passport/{id}",
            "dpp_json": "/api/dpp/{id}?view=consumer|b2b|authority",
            "dpp_public_html": "/dpp/{id}",
            "dpp_field_catalog": "/api/dpp/field-catalog",
            "csv_export": "/api/export/products.csv",
            "metadata": "/api/data-product",
            "lineage": "/api/lineage",
            "access_policy": "/api/access-policy",
        },
        "mandatory_metadata": METADATA_CONFIG.get("mandatory_metadata", []),
        "sync": {
            "enabled": sync_config.get("enabled"),
            "mode": sync_config.get("mode"),
            "source_url": sync_config.get("source_url"),
            "contract": sync_config.get("contract"),
            "state": store.sync_state,
        },
        "effective_access": {
            "role": user.get("role"),
            "region": user.get("region"),
            "purpose": user.get("purpose"),
            "permissions": permissions,
            "can_import": has_permission(user, "product:import"),
            "can_read_all_regions": has_permission(user, "product:read_all_regions"),
        },
    }


def lineage_surface(store: ProductStore) -> dict[str, Any]:
    return {
        "contract": METADATA_CONFIG.get("lineage_contract", {}),
        "current_sync": store.sync_state,
        "nodes": [
            {"id": "source-documents", "layer": "raw", "owner": "central data platform"},
            {"id": "paul-ai-ingest", "layer": "raw", "owner": "data-layer"},
            {"id": "data-layer-postgres", "layer": "standardized", "owner": "data-layer"},
            {"id": "curated_product.product_master_dpp", "layer": "curated", "owner": "Product Data Domain"},
            {"id": "product-layer-json-store", "layer": "consumption", "owner": "Product Data Domain"},
            {"id": "product-layer-rest-ui-export", "layer": "consumption", "owner": "Product Data Domain"},
        ],
        "edges": [
            ["source-documents", "paul-ai-ingest"],
            ["paul-ai-ingest", "data-layer-postgres"],
            ["data-layer-postgres", "curated_product.product_master_dpp"],
            ["curated_product.product_master_dpp", "product-layer-json-store"],
            ["product-layer-json-store", "product-layer-rest-ui-export"],
        ],
    }


def access_policy_surface(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "effective_user": {
            "role": user.get("role"),
            "purpose": user.get("purpose"),
            "region": user.get("region"),
            "permissions": role_permissions(user.get("role", "viewer")),
        },
        "authentication": {
            "mode": "token-gated-role-headers" if os.environ.get("THEBEN_ROLE_TOKEN") else "local-trusted-role-headers",
            "role_header": "X-Role",
            "token_headers": ["X-Role-Token", "Authorization: Bearer <token>"],
        },
        "roles": ACCESS_CONFIG.get("roles", {}),
        "abac_attributes": ACCESS_CONFIG.get("abac_attributes", []),
        "row_level_security": ACCESS_CONFIG.get("row_level_security", []),
        "masking": ACCESS_CONFIG.get("masking", {}),
        "layer_access": ACCESS_CONFIG.get("layer_access", {}),
    }


def dpp_view_for_user(user: dict[str, Any], query: dict[str, list[str]] | None = None) -> str:
    requested = requested_dpp_view(query or {})
    if dpp_view_allowed(user, requested):
        return requested
    return "consumer"


def passport(product: dict[str, Any]) -> dict[str, Any]:
    attrs = product.get("attributes", {})
    identity = product_identity(product)
    return {
        "passport_version": "0.1.0",
        "product": {
            "sku": product.get("sku"),
            "name": product.get("name"),
            "family": product.get("family"),
            "lifecycle_status": product.get("lifecycle_status"),
        },
        "identity": {
            **identity,
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
            "/api/sync/data-layer": {
                "get": {"summary": "Inspect configured data-layer synchronization contract and last sync state"},
                "post": {"summary": "Synchronize product-layer from the PAUL data-layer export contract"},
            },
            "/api/integrations/data-layer": {"get": {"summary": "Describe the configured data-layer interface contract"}},
            "/api/data-product": {"get": {"summary": "Describe the governed product data product, interfaces, and caller access"}},
            "/api/catalog/data-products": {"get": {"summary": "List governed product-layer data products and metadata requirements"}},
            "/api/lineage": {"get": {"summary": "Describe lakehouse layer lineage for the product data product"}},
            "/api/access-policy": {"get": {"summary": "Expose access policy and caller-effective permissions"}},
            "/api/dpp/{id}": {
                "get": {"summary": "Role-filtered EU Digital Product Passport record"},
                "patch": {"summary": "Update DPP-relevant product metadata and attributes, then version the DPP record"},
                "post": {"summary": "Update DPP-relevant product metadata and attributes, then version the DPP record"},
            },
            "/api/dpp/{id}/versions": {"get": {"summary": "DPP lifecycle and version history"}},
            "/api/dpp/{id}/audit": {"get": {"summary": "DPP audit trail surface"}},
            "/api/dpp/scan": {"get": {"summary": "Resolve a Data Matrix encoded public URL or structured identifier"}},
            "/dpp/{id}": {"get": {"summary": "Public, no-login DPP HTML view for label scans"}},
            "/api/validation/status": {"get": {"summary": "Run product quality validation"}},
            "/api/summary": {"get": {"summary": "Visualization-ready aggregate summary"}},
            "/api/passport/{id}": {"get": {"summary": "Digital Product Passport JSON preview"}},
            "/api/dpp/field-catalog": {"get": {"summary": "JRC three-tier DPP field catalog"}},
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
        if path == "/api/catalog/data-products":
            return self.send_json(catalog_data_products())
        if path == "/api/dpp/field-catalog":
            return self.send_json(dpp_field_catalog())
        if path == "/api/data-product":
            return self.send_json(data_product_surface(self.store, user))
        if path == "/api/lineage":
            return self.send_json({**lineage_model(), "sync_state": self.store.sync_state})
        if path == "/api/access-policy":
            return self.send_json(access_policy_surface(user))
        if path == "/api/integrations/data-layer":
            return self.send_json(data_layer_contract())
        if path == "/api/sync/data-layer":
            surface = data_product_surface(self.store, user)
            return self.send_json({"sync": surface["sync"], "effective_access": surface["effective_access"]})
        if path == "/api/dpp/scan":
            return self.resolve_dpp_scan(query, user)
        if path.startswith("/api/dpp/") and path.endswith("/versions"):
            product_id = path.removeprefix("/api/dpp/").removesuffix("/versions").rstrip("/")
            product = self.store.get_raw_product(product_id)
            return self.send_json_or_404(dpp_versions(product) if product else None, "DPP record not found")
        if path.startswith("/api/dpp/") and path.endswith("/audit"):
            product_id = path.removeprefix("/api/dpp/").removesuffix("/audit").rstrip("/")
            if not has_permission(user, "product:read_all_regions"):
                return self.send_error_json(HTTPStatus.FORBIDDEN, "authority access required")
            product = self.store.get_raw_product(product_id)
            return self.send_json_or_404(
                dpp_audit(product, self.store.audit_for_product(product_id)) if product else None,
                "DPP record not found",
            )
        if path.startswith("/api/dpp/"):
            product_id = path.removeprefix("/api/dpp/")
            view = dpp_view_for_user(user, query)
            product = self.store.get_raw_product(product_id) if view == "consumer" else self.store.get_product(product_id, user)
            if not product:
                return self.send_json_or_404(None, "DPP record not found")
            event = self.store.record_audit(
                action="dpp_json_read",
                product_id=product_id,
                role=user.get("role", "viewer"),
                actor=user.get("actor"),
                view=view,
                channel="api",
            )
            audit_events = self.store.audit_for_product(product_id) if view == "authority" else [event]
            return self.send_json(dpp_record(product, view, dpp_public_base_url(self.headers.get("Host", "localhost")), audit_events))
        if path.startswith("/dpp/"):
            product_id = path.removeprefix("/dpp/")
            product = self.store.get_raw_product(product_id)
            if not product:
                return self.send_bytes(not_found_html("DPP record not found"), HTML, status=HTTPStatus.NOT_FOUND)
            self.store.record_audit(
                action="dpp_public_html_read",
                product_id=product_id,
                role="anonymous",
                actor="anonymous",
                view="consumer",
                channel="public-html",
            )
            return self.send_bytes(public_dpp_html(product, dpp_public_base_url(self.headers.get("Host", "localhost"))), HTML)
        if path == "/api/products":
            products = self.store.list_products(query, user)
            self.audit_read("product_list_read", "bulk-products", user, {"count": len(products)})
            return self.send_json({"products": products})
        if path.startswith("/api/products/"):
            product_id = path.removeprefix("/api/products/")
            product = self.store.get_product(product_id, user)
            if product:
                self.audit_read("product_read", product_id, user)
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
            self.audit_read("validation_status_read", "bulk-validation", user, {"count": len(results)})
            return self.send_json({"counts": counts, "results": results})
        if path == "/api/summary":
            products = self.store.list_products({"limit": ["1000"]}, user)
            self.audit_read("summary_read", "bulk-summary", user, {"count": len(products)})
            return self.send_json(summary(products))
        if path.startswith("/api/passport/"):
            product_id = path.removeprefix("/api/passport/")
            product = self.store.get_product(product_id, user)
            if product:
                self.audit_read("passport_json_read", product_id, user)
            return self.send_json_or_404(passport(product) if product else None, "product not found")
        if path == "/api/export/products.csv":
            products = self.store.list_products({"limit": ["1000"]}, user)
            self.audit_read("products_csv_export", "bulk-products", user, {"count": len(products)})
            return self.send_bytes(products_csv(products), CSV_MIME, "products.csv")
        if path.startswith("/api/export/passport/") and path.endswith(".html"):
            product_id = path.removeprefix("/api/export/passport/").removesuffix(".html")
            product = self.store.get_product(product_id, user)
            if product:
                self.audit_read("passport_html_export", product_id, user)
            return self.send_bytes(passport_html(product) if product else not_found_html("product not found"), HTML)
        if path.startswith("/api/export/passport/") and path.endswith(".svg"):
            product_id = path.removeprefix("/api/export/passport/").removesuffix(".svg")
            product = self.store.get_product(product_id, user)
            if product:
                self.audit_read("passport_svg_export", product_id, user)
            return self.send_bytes(passport_svg(product) if product else not_found_svg("product not found"), SVG)
        return super().do_GET()

    def resolve_dpp_scan(self, query: dict[str, list[str]], user: dict[str, Any]) -> None:
        code = query.get("code", [""])[0].strip()
        if not code:
            return self.send_error_json(HTTPStatus.BAD_REQUEST, "code query parameter required")
        with self.store.lock:
            products = list(self.store.products)
        host = self.headers.get("Host", "localhost")
        for product in products:
            record = dpp_record(product, "consumer", dpp_public_base_url(host))
            if code in (
                record["public_url"],
                record["data_matrix"]["encoded_content"],
                record["data_matrix"]["structured_identifier"],
                record["identity"]["globally_unique_instance_id"],
            ):
                self.store.record_audit(
                    action="dpp_public_scan_resolve",
                    product_id=str(product.get("id")),
                    role="anonymous",
                    actor="anonymous",
                    view="consumer",
                    channel="public-scan",
                )
                return self.send_json({"record": record})
        return self.send_error_json(HTTPStatus.NOT_FOUND, "DPP record not found")

    def audit_read(
        self,
        action: str,
        product_id: str,
        user: dict[str, Any],
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.store.record_audit(
            action=action,
            product_id=product_id,
            role=user.get("role", "viewer"),
            actor=user.get("actor"),
            view="read",
            channel="api",
            details=details,
        )

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
            self.store.record_audit(
                action="product_upsert",
                product_id=product["id"],
                role=user.get("role", "viewer"),
                actor=user.get("actor"),
                view="internal",
                channel="api",
            )
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
            result = self.store.import_products(products)
            self.store.record_audit(
                action="product_import",
                product_id="bulk-import",
                role=user.get("role", "viewer"),
                actor=user.get("actor"),
                view="internal",
                channel="api",
            )
            return self.send_json(result, HTTPStatus.CREATED)
        if parsed.path == "/api/sync/data-layer":
            if not has_permission(user, "product:import"):
                return self.send_error_json(HTTPStatus.FORBIDDEN, "missing product:import permission")
            contract = data_layer_contract()
            try:
                result = sync_from_data_layer(self.store)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                return self.send_error_json(HTTPStatus.BAD_GATEWAY, f"data-layer sync failed: {exc}")
            self.store.record_audit(
                action="data_layer_sync",
                product_id="bulk-sync",
                role=user.get("role", "viewer"),
                actor=user.get("actor"),
                view="internal",
                channel="api",
            )
            return self.send_json(
                {
                    "source": result["source"].get("url"),
                    "source_schema_version": result["source"].get("schema_version"),
                    "source_generated_at": result["source"].get("generated_at"),
                    "target_data_product": contract["target_data_product"],
                    "result": result,
                    "sync_state": self.store.sync_state,
                    "synced_at": utc_now(),
                },
                HTTPStatus.CREATED,
            )
        if parsed.path.startswith("/api/dpp/"):
            return self.update_dpp(parsed.path, user)
        return self.send_error_json(HTTPStatus.NOT_FOUND, "endpoint not found")

    def do_PATCH(self) -> None:
        parsed = urlparse(self.path)
        user = current_user(self.headers)
        if parsed.path.startswith("/api/dpp/"):
            return self.update_dpp(parsed.path, user)
        if parsed.path.startswith("/api/products/") and parsed.path.endswith("/attributes"):
            if not has_permission(user, "product:write"):
                return self.send_error_json(HTTPStatus.FORBIDDEN, "missing product:write permission")
            product_id = parsed.path.removeprefix("/api/products/").removesuffix("/attributes").rstrip("/")
            payload = self.read_json()
            attributes = payload.get("attributes", payload)
            if not isinstance(attributes, dict):
                return self.send_error_json(HTTPStatus.BAD_REQUEST, "attributes object required")
            product = self.store.patch_attributes(product_id, attributes)
            if product:
                self.store.record_audit(
                    action="product_attribute_patch",
                    product_id=product_id,
                    role=user.get("role", "viewer"),
                    actor=user.get("actor"),
                    view="internal",
                    channel="api",
                )
            return self.send_json_or_404({"product": product} if product else None, "product not found")
        return self.send_error_json(HTTPStatus.NOT_FOUND, "endpoint not found")

    def update_dpp(self, path: str, user: dict[str, Any]) -> None:
        if not has_permission(user, "product:write"):
            return self.send_error_json(HTTPStatus.FORBIDDEN, "missing product:write permission")
        product_id = path.removeprefix("/api/dpp/").rstrip("/")
        if not product_id or "/" in product_id:
            return self.send_error_json(HTTPStatus.NOT_FOUND, "endpoint not found")
        try:
            payload = self.read_json()
            product = self.store.update_dpp_record(product_id, payload, user)
        except ValueError as exc:
            return self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
        if not product:
            return self.send_json_or_404(None, "DPP record not found")
        metadata = product.get("metadata", {})
        event = self.store.record_audit(
            action="dpp_record_update",
            product_id=product_id,
            role=user.get("role", "viewer"),
            actor=user.get("actor"),
            view="authority",
            channel="api",
            details={
                "dpp_version": metadata.get("dpp_version"),
                "change_rationale": metadata.get("change_rationale"),
            },
        )
        view = dpp_view_for_user(user, {})
        audit_events = self.store.audit_for_product(product_id) if view == "authority" else [event]
        return self.send_json(dpp_record(product, view, dpp_public_base_url(self.headers.get("Host", "localhost")), audit_events))

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
        path = urlparse(self.path).path
        self.send_header("Content-Type", content_type)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self' 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'",
        )
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Role, X-Role-Token, X-Purpose, X-Region")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
        if path.startswith("/api/"):
            self.send_header("Cache-Control", "no-store")
            self.send_header("Pragma", "no-cache")
        elif path.startswith("/dpp/") and content_type.startswith("text/html"):
            self.send_header("Cache-Control", "public, max-age=60, stale-while-revalidate=300")
        else:
            self.send_header("Cache-Control", "public, max-age=300")


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
                    attr = key.removeprefix("attributes.")
                    attributes[attr] = value if attr in IDENTITY_STRING_ATTRIBUTES else coerce_value(value)
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
        "attributes.batch_lot_number",
        "attributes.serial_number",
        "identity.gtin_14",
        "identity.globally_unique_instance_id",
        "identity.data_matrix.payload",
        "attributes.co2_kg",
        "attributes.recyclable_share_pct",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for product in products:
        export_product = {**product, "identity": product_identity(product)}
        row = {}
        for field in fields:
            value = nested_value(export_product, field)
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


def dpp_public_html(product: dict[str, Any], host: str) -> str:
    record = dpp_record(product, "consumer", host)
    field_sections = []
    for field in record["fields"]:
        value = field.get("value")
        if isinstance(value, dict):
            rows = "".join(
                f"<tr><th>{html.escape(str(key).replace('_', ' ').title())}</th><td>{html.escape(format_public_value(val))}</td></tr>"
                for key, val in value.items()
            )
            content = f"<table>{rows}</table>"
        else:
            content = f"<p>{html.escape(format_public_value(value))}</p>"
        field_sections.append(
            f"""<section class="panel dpp-section" data-tier="{html.escape(str(field.get("tier")))}">
      <h2>{html.escape(str(field.get("label")))}</h2>
      <p class="muted">{html.escape(str(field.get("tier")).replace("_", " ").title())} | {html.escape(str(field.get("granularity")).title())}</p>
      {content}
    </section>"""
        )
    structured = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product.get("name"),
        "sku": product.get("sku"),
        "gtin": record["identity"].get("gtin"),
        "manufacturer": {"@type": "Organization", "name": "Theben AG"},
        "url": record["public_url"],
        "identifier": record["identity"].get("globally_unique_instance_id"),
    }
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DPP {html.escape(str(product.get("sku")))}</title>
  <link rel="stylesheet" href="/styles.css">
  <script type="application/ld+json">{json_for_script(structured)}</script>
</head>
<body class="dpp-public">
  <header class="topbar">
    <div>
      <h1>Digital Product Passport</h1>
      <p>{html.escape(str(product.get("name")))} | {html.escape(str(product.get("sku")))}</p>
    </div>
  </header>
  <main class="dpp-page">
    <section class="panel dpp-identity">
      <h2>Public Product Identifier</h2>
      <table>
        <tr><th>GTIN</th><td>{html.escape(str(record["identity"]["gtin"]))}</td></tr>
        <tr><th>Batch/Lot</th><td>{html.escape(str(record["identity"]["batch_lot_number"]))}</td></tr>
        <tr><th>Serial</th><td>{html.escape(str(record["identity"]["serial_number"]))}</td></tr>
        <tr><th>Data Matrix URL</th><td>{html.escape(str(record["data_matrix"]["encoded_content"]))}</td></tr>
        <tr><th>Structured Identifier</th><td>{html.escape(str(record["data_matrix"]["structured_identifier"]))}</td></tr>
      </table>
    </section>
    {"".join(field_sections)}
    <footer class="muted">Record {html.escape(str(record["record_version"]))} | Status {html.escape(str(record["status"]))} | Free public access, no login required.</footer>
  </main>
</body>
</html>"""


def format_public_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(format_public_value(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value)


def dpp_value_text(value: Any) -> str:
    if isinstance(value, list):
        if value and all(isinstance(item, dict) for item in value):
            return "; ".join(str(item.get("name") or item.get("source_uri") or item) for item in value)
        return ", ".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    if value is None:
        return "Not available"
    return str(value)


def dpp_field_map(record: dict[str, Any]) -> dict[str, Any]:
    return {field["key"]: field.get("value") for field in record.get("fields", [])}


def dpp_json_ld(record: dict[str, Any]) -> str:
    fields = dpp_field_map(record)
    payload = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": fields.get("product_name"),
        "model": fields.get("model"),
        "category": fields.get("product_family"),
        "gtin": fields.get("gtin"),
        "manufacturer": {
            "@type": "Organization",
            "name": fields.get("manufacturer_name"),
            "address": fields.get("manufacturer_address"),
        },
        "material": fields.get("main_materials"),
        "url": record.get("data_carrier", {}).get("public_url"),
        "identifier": record.get("identifiers", {}).get("globally_unique_instance_id"),
    }
    return json.dumps(payload, sort_keys=True)


def public_dpp_html(product: dict[str, Any], public_base_url: str) -> str:
    record = dpp_record(product, "consumer", public_base_url)
    fields = record["fields"]
    product_name = next((field["value"] for field in fields if field["key"] == "product_name"), product.get("name"))
    rows = "".join(
        "<tr>"
        f"<th>{html.escape(field['label'])}</th>"
        f"<td>{html.escape(dpp_value_text(field.get('value')))}</td>"
        f"<td>{html.escape(field['classification'])}</td>"
        f"<td>{html.escape(field['granularity'])}</td>"
        "</tr>"
        for field in fields
    )
    carrier = record["data_carrier"]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DPP {html.escape(str(product.get("sku")))}</title>
  <link rel="stylesheet" href="/styles.css">
  <script type="application/ld+json">{json_for_script(dpp_json_ld(record))}</script>
</head>
<body class="print public-dpp">
  <main>
	    <section class="dpp-hero">
	      <p class="muted">EU Digital Product Passport</p>
	      <h1>{html.escape(dpp_value_text(product_name))}</h1>
	      <p>{html.escape(str(product.get("sku")))} | {html.escape(str(product.get("family")))} | {html.escape(record["lifecycle"]["dpp_status"])}</p>
	      <p>Free public access, no login required.</p>
	    </section>
    <section class="dpp-summary">
      <h2>Data carrier</h2>
      <dl>
        <dt>Encoded content</dt><dd>{html.escape(carrier["encoded_content"])}</dd>
        <dt>Carrier</dt><dd>{html.escape(carrier["symbology"])}</dd>
        <dt>Placement</dt><dd>{html.escape(carrier["placement"])}</dd>
        <dt>Durability</dt><dd>{html.escape(carrier["print_quality"]["durability"])}</dd>
      </dl>
    </section>
    <section>
      <h2>Consumer DPP fields</h2>
      <table>
        <thead><tr><th>Field</th><th>Value</th><th>JRC tier</th><th>Granularity</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </section>
    <section>
      <h2>Lifecycle</h2>
      <p>Version {html.escape(record["lifecycle"]["version"])}. Last updated {html.escape(str(record["lifecycle"]["updated_at"]))}.</p>
      <p>{html.escape(record["lifecycle"]["useful_life_commitment"])}</p>
    </section>
    <footer>Generated {html.escape(record["generated_at"])} from the product-layer DPP model.</footer>
  </main>
</body>
</html>"""


def passport_html(product: dict[str, Any]) -> str:
    return public_dpp_html(product, "http://localhost")


def passport_svg(product: dict[str, Any]) -> str:
    p = passport(product)
    name = html.escape(str(p["product"]["name"]))
    sku = html.escape(str(p["product"]["sku"]))
    family = html.escape(str(p["product"]["family"]))
    status = html.escape(str(p["compliance"]["certification_status"]))
    certs = html.escape(", ".join(p["compliance"]["certifications"]))
    gtin = html.escape(str(p["identity"]["gtin"]))
    batch = html.escape(str(p["identity"]["batch_lot_number"]))
    serial = html.escape(str(p["identity"]["serial_number"]))
    data_matrix = html.escape(str(p["identity"]["data_matrix"]["payload"]))
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
  <text x="560" y="282" fill="#1d2a25" font-family="Arial, sans-serif" font-size="24">Identity</text>
  <text x="560" y="320" fill="#42534b" font-family="Arial, sans-serif" font-size="18">GTIN: {gtin}</text>
  <text x="560" y="350" fill="#42534b" font-family="Arial, sans-serif" font-size="18">Batch/Lot: {batch}</text>
  <text x="560" y="380" fill="#42534b" font-family="Arial, sans-serif" font-size="18">Serial: {serial}</text>
  <text x="72" y="402" fill="#42534b" font-family="Arial, sans-serif" font-size="16">Data Matrix: {data_matrix}</text>
  <text x="560" y="432" fill="#42534b" font-family="Arial, sans-serif" font-size="18">CO2: {co2} kg | Recyclable: {rec}%</text>
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


def _startup_sync(store: ProductStore) -> None:
    """Attempt data-layer sync on startup. Non-fatal if data-layer is unreachable."""
    try:
        config = data_layer_sync_config()
        if not config.get("enabled"):
            logger.info("STARTUP-SYNC: disabled via config")
            return
        result = sync_from_data_layer(store, config)
        logger.info("STARTUP-SYNC: success — %d products synced", result.get("imported", 0))
    except Exception as exc:
        logger.warning("STARTUP-SYNC: data-layer not reachable (%s) — using local store", exc)


def _file_watcher(store: ProductStore) -> None:
    """Watch products.json for external changes (data-layer writing directly) and reload."""
    path = store.path
    last_mtime = path.stat().st_mtime if path.exists() else 0
    while True:
        time.sleep(2)
        try:
            if not path.exists():
                continue
            mtime = path.stat().st_mtime
            if mtime > last_mtime:
                last_mtime = mtime
                old_count = len(store.products)
                store.load()
                new_count = len(store.products)
                if new_count != old_count:
                    logger.info("FILE-WATCH: products.json changed externally, reloaded (%d -> %d products)",
                                old_count, new_count)
        except Exception:
            pass  # watcher must never crash


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Thebenpaul product-layer MVP")
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8080")))
    parser.add_argument("--no-sync", action="store_true", help="Skip startup sync from data-layer")
    args = parser.parse_args(argv)
    server = make_server(args.host, args.port)
    if not args.no_sync:
        _startup_sync(server.store)  # type: ignore[attr-defined]
    watcher = threading.Thread(target=_file_watcher, args=(server.store,), daemon=True)  # type: ignore[attr-defined]
    watcher.start()
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
