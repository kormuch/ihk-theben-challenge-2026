#!/usr/bin/env python3
"""Theben-styled competition report service."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, unquote, urlparse
from urllib.request import Request, urlopen

try:  # Optional locally; installed in Docker.
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
except Exception:  # pragma: no cover - fallback path is tested without reportlab.
    A4 = None
    colors = None
    getSampleStyleSheet = None
    Image = PageBreak = Paragraph = ParagraphStyle = SimpleDocTemplate = Spacer = Table = TableStyle = None


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("theben-layer")


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
DATA_DIR = Path(os.environ.get("THEBEN_LAYER_DATA_DIR", str(ROOT / "data")))
FIXTURE_PATH = DATA_DIR / "fixtures" / "legacy_fixture.json"
REPORT_DIR = DATA_DIR / "reports"
SBOM_DIR = DATA_DIR / "sbom"
CVE_DIR = DATA_DIR / "cve"
VEX_DIR = DATA_DIR / "vex"
ASSET_DIR = ROOT / "assets"
LOGO_PATH = Path(os.environ.get("THEBEN_LOGO_PATH", str(ASSET_DIR / "logo_theben.jpg")))

JSON_MIME = "application/json; charset=utf-8"
HTML_MIME = "text/html; charset=utf-8"
PDF_MIME = "application/pdf"

SAFE_DISCOVERY_PATHS = [
    "/openapi.json",
    "/swagger.json",
    "/docs",
    "/redoc",
    "/products/sbom",
    "/products/software",
    "/products/firmware",
    "/products/components",
    "/products/vulnerabilities",
    "/products/cves",
    "/products/vex",
    "/products/compliance",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slug(raw: Any) -> str:
    text = str(raw or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "unknown"


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def file_sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_config() -> dict[str, Any]:
    path = Path(os.environ.get("THEBEN_LAYER_CONFIG", str(CONFIG_DIR / "runtime.json")))
    if not path.exists():
        return {}
    return read_json(path)


def load_fixture() -> dict[str, Any]:
    return read_json(FIXTURE_PATH)


class LegacyClient:
    def __init__(self, base_url: str, timeout: float = 5.0, use_fixture: bool = False) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.use_fixture = use_fixture
        self.fixture = load_fixture() if use_fixture else None

    def get_json(self, path: str) -> Any:
        if self.fixture is not None:
            return fixture_response(self.fixture, path)
        request = Request(f"{self.base_url}{path}", headers={"Accept": "application/json"})
        with urlopen(request, timeout=self.timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else None

    def list_products(self) -> list[dict[str, Any]]:
        payload = self.get_json("/products")
        return payload if isinstance(payload, list) else payload.get("products", [])

    def bom(self, article_number: str) -> dict[str, Any]:
        return self.get_first([
            article_path("/products/bom", article_number, "articlenumber"),
            article_path("/products/bom", article_number, "articleNumber"),
        ])

    def certificate(self, article_number: str) -> dict[str, Any]:
        return self.get_first([
            article_path("/products/certificate", article_number, "articlenumber"),
            article_path("/products/certificate", article_number, "articleNumber"),
        ])

    def sbom(self, article_number: str) -> dict[str, Any] | None:
        return self.try_get_first([
            article_path("/products/sbom", article_number, "articlenumber"),
            article_path("/products/sbom", article_number, "articleNumber"),
        ])

    def vulnerabilities(self, article_number: str) -> dict[str, Any] | list[dict[str, Any]] | None:
        return self.try_get_first([
            article_path("/products/vulnerabilities", article_number, "articlenumber"),
            article_path("/products/vulnerabilities", article_number, "articleNumber"),
        ])

    def get_first(self, paths: list[str]) -> Any:
        errors = []
        for path in paths:
            try:
                return self.get_json(path)
            except Exception as exc:
                errors.append(f"{path}: {exc}")
        raise RuntimeError("; ".join(errors))

    def try_get(self, path: str) -> Any | None:
        try:
            return self.get_json(path)
        except Exception as exc:
            logger.info("optional legacy path unavailable %s: %s", path, exc)
            return None

    def try_get_first(self, paths: list[str]) -> Any | None:
        for path in paths:
            payload = self.try_get(path)
            if payload is not None:
                return payload
        return None

    def discover(self) -> list[dict[str, Any]]:
        results = []
        for path in SAFE_DISCOVERY_PATHS:
            started = time.time()
            item = {"method": "GET", "path": path, "url": f"{self.base_url}{path}"}
            try:
                if self.fixture is not None:
                    fixture_response(self.fixture, path)
                    item.update({"status": 200, "available": True})
                else:
                    request = Request(f"{self.base_url}{path}", method="GET", headers={"Accept": "application/json"})
                    with urlopen(request, timeout=min(self.timeout, 3.0)) as response:
                        item.update({"status": response.status, "available": response.status < 400})
            except HTTPError as exc:
                item.update({"status": exc.code, "available": False})
            except URLError as exc:
                item.update({"status": "unreachable", "available": False, "error": str(exc.reason)})
            except Exception as exc:
                item.update({"status": "error", "available": False, "error": str(exc)})
            item["latency_ms"] = round((time.time() - started) * 1000, 2)
            results.append(item)
        return results


def fixture_response(fixture: dict[str, Any], path: str) -> Any:
    parsed = urlparse(path)
    query = parse_qs(parsed.query)
    article = (query.get("articlenumber") or query.get("articleNumber") or [""])[0]
    if parsed.path == "/products":
        return fixture["products"]
    if parsed.path == "/products/bom":
        return fixture["boms"][article]
    if parsed.path == "/products/certificate":
        return fixture["certificates"][article]
    if parsed.path == "/products/sbom":
        return fixture["sboms"][article]
    if parsed.path == "/products/vulnerabilities":
        return fixture["vulnerabilities"][article]
    if parsed.path in SAFE_DISCOVERY_PATHS:
        return {"status": "fixture", "path": parsed.path}
    raise KeyError(path)


def article_path(path: str, article_number: str, parameter_name: str = "articlenumber") -> str:
    return f"{path}?{parameter_name}={quote(str(article_number), safe='')}"


def normalize_product(product: dict[str, Any]) -> dict[str, Any]:
    article = str(product.get("articleNumber") or product.get("article_number") or product.get("sku") or "").strip()
    if not article:
        raise ValueError("legacy product missing articleNumber")
    return {
        "article_number": article,
        "name": product.get("name") or article,
        "category": product.get("category") or "Unsorted",
        "source_system": "proprietary-rest-system",
        "source_base_url": os.environ.get("THEBEN_LEGACY_BASE_URL", "http://192.168.8.200:8000"),
    }


def normalize_components(sbom_payload: Any, bom_payload: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(sbom_payload, dict) and isinstance(sbom_payload.get("components"), list):
        return sbom_payload["components"]
    components = []
    for item in bom_payload.get("bom", []):
        part = item.get("partNumber") or item.get("part_number") or item.get("description")
        components.append({
            "type": "hardware",
            "name": item.get("description") or part,
            "version": item.get("version") or "unknown",
            "supplier": item.get("supplier") or "unknown",
            "purl": f"pkg:generic/{slug(part)}",
            "licenses": [],
        })
    return components


def build_cyclonedx(product: dict[str, Any], bom: dict[str, Any], sbom_payload: Any) -> dict[str, Any]:
    components = normalize_components(sbom_payload, bom)
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{hashlib.md5(product['article_number'].encode()).hexdigest()}",
        "version": 1,
        "metadata": {
            "timestamp": utc_now(),
            "component": {
                "type": "device",
                "name": product["name"],
                "version": product["article_number"],
            },
            "properties": [
                {"name": "thebenpaul:source_system", "value": "proprietary-rest-system"},
                {"name": "thebenpaul:classification", "value": "internal"},
            ],
        },
        "components": components,
    }


def vulnerability_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("vulnerabilities", "cves", "items"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return []


def normalized_cve_id(item: dict[str, Any]) -> str:
    raw = str(item.get("cve") or item.get("id") or item.get("cveId") or "UNKNOWN-CVE").strip().upper()
    if re.match(r"^CVE-\d{4}-\d{4,}$", raw):
        return raw
    return "UNKNOWN-CVE"


def component_refs_for_vulnerability(sbom: dict[str, Any], item: dict[str, Any]) -> list[dict[str, Any]]:
    raw_component = str(item.get("component") or item.get("component_name") or item.get("package") or "").strip().lower()
    components = sbom.get("components") or []
    matches = []
    for component in components:
        name = str(component.get("name") or "").strip()
        purl = str(component.get("purl") or "").strip()
        if not raw_component or raw_component in name.lower() or raw_component in purl.lower():
            matches.append(
                {
                    "name": name,
                    "version": component.get("version") or "unknown",
                    "purl": purl or f"pkg:generic/{slug(name)}",
                }
            )
    return matches[:8]


def cve_references(item: dict[str, Any], cve_id: str) -> list[str]:
    refs = item.get("references") or item.get("refs") or []
    if isinstance(refs, str):
        refs = [refs]
    result = [str(ref).strip() for ref in refs if str(ref).strip()]
    if cve_id != "UNKNOWN-CVE" and not result:
        result.append(f"https://nvd.nist.gov/vuln/detail/{cve_id}")
    vendor = item.get("vendor_advisory") or item.get("advisory")
    if vendor:
        result.append(str(vendor))
    return list(dict.fromkeys(result))


def build_cve_export(product: dict[str, Any], sbom: dict[str, Any], vulnerability_payload: Any) -> dict[str, Any]:
    cves = []
    for item in vulnerability_items(vulnerability_payload):
        cve_id = normalized_cve_id(item)
        cves.append(
            {
                "cveId": cve_id,
                "description": item.get("description") or item.get("title") or f"{cve_id} requires product security review.",
                "severity": str(item.get("severity") or "UNKNOWN").upper(),
                "references": cve_references(item, cve_id),
                "affected_components": component_refs_for_vulnerability(sbom, item),
                "source": item.get("source") or "proprietary-rest-vulnerability-endpoint",
                "status": item.get("status") or item.get("vex_status") or "under_investigation",
            }
        )
    return {
        "schema": "thebenpaul-cve-export-v1",
        "generated_at": utc_now(),
        "product": {
            "article_number": product["article_number"],
            "name": product["name"],
            "purl": product_purl(product),
        },
        "matching_method": "SBOM component/version data matched against proprietary REST vulnerability records; external CVE database enrichment can be added behind the same export contract.",
        "cves": cves,
    }


def product_purl(product: dict[str, Any]) -> str:
    return f"pkg:firmware/theben/{slug(product['article_number'])}@{slug(product.get('version') or product['article_number'])}"


def build_openvex(product: dict[str, Any], sbom: dict[str, Any], vulnerability_payload: Any) -> dict[str, Any]:
    statements = []
    for item in vulnerability_items(vulnerability_payload):
        cve_id = normalized_cve_id(item)
        status = item.get("status") or item.get("vex_status") or "under_investigation"
        statement = {
            "vulnerability": {
                "@id": f"https://nvd.nist.gov/vuln/detail/{cve_id}" if cve_id != "UNKNOWN-CVE" else "urn:thebenpaul:vulnerability:unknown",
                "name": cve_id,
            },
            "status": status,
            "justification": item.get("justification") or default_vex_justification(status),
        }
        impact = item.get("impact_statement") or item.get("impact")
        action = item.get("action_statement") or item.get("remediation") or item.get("remediation_plan")
        if impact:
            statement["impact_statement"] = str(impact)
        if action:
            statement["action_statement"] = str(action)
        components = component_refs_for_vulnerability(sbom, item)
        if components:
            statement["subcomponents"] = [{"@id": component["purl"], "name": component["name"]} for component in components]
        statements.append(statement)
    return {
        "@context": "https://openvex.dev/ns/v0.2.0",
        "@id": f"https://theben.de/vex/{slug(product['article_number'])}.vex",
        "author": "Theben Security Team",
        "timestamp": utc_now(),
        "version": 1,
        "product": {
            "@id": product_purl(product),
            "name": product["name"],
        },
        "statements": statements,
    }


def default_vex_justification(status: str) -> str:
    normalized = str(status or "").lower()
    if normalized == "not_affected":
        return "vulnerable_code_not_in_execute_path"
    if normalized == "fixed":
        return "fixed_in_current_firmware_baseline"
    if normalized == "affected":
        return "code_present"
    return "under_investigation"


def build_vex(product: dict[str, Any], sbom: dict[str, Any], vulnerability_payload: Any) -> dict[str, Any]:
    vulns = []
    for item in vulnerability_items(vulnerability_payload):
        cve = item.get("cve") or item.get("id") or item.get("cveId") or "UNKNOWN-CVE"
        status = item.get("status") or item.get("vex_status") or "under_investigation"
        vulns.append({
            "cve": cve,
            "title": item.get("title") or cve,
            "severity": item.get("severity") or "unknown",
            "product_status": {
                status: [product["article_number"]],
            },
            "notes": [
                {
                    "category": "description",
                    "text": item.get("justification") or item.get("description") or "Derived from proprietary REST vulnerability data.",
                }
            ],
        })
    return {
        "document": {
            "category": "csaf_vex",
            "title": f"Thebenpaul VEX overview - {product['name']}",
            "tracking": {
                "id": f"thebenpaul-vex-{slug(product['article_number'])}",
                "status": "draft",
                "version": "1.0.0",
                "initial_release_date": utc_now(),
                "current_release_date": utc_now(),
            },
        },
        "product_tree": {
            "branches": [
                {
                    "category": "product_name",
                    "name": product["name"],
                    "product": {
                        "product_id": product["article_number"],
                        "name": product["name"],
                    },
                }
            ]
        },
        "vulnerabilities": vulns,
        "sbom_reference": f"{slug(product['article_number'])}.cyclonedx.json",
    }


def select_demo_products(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = [normalize_product(p) for p in products]
    preferred = []
    for needle in ("vacuum", "coffee"):
        found = next(
            (
                p for p in normalized
                if needle in p["name"].lower() or needle in p["category"].lower() or needle in p["article_number"].lower()
            ),
            None,
        )
        if found and found not in preferred:
            preferred.append(found)
    for product in normalized:
        if len(preferred) >= 2:
            break
        if product not in preferred:
            preferred.append(product)
    return preferred[:2]


def selected_article_candidates(selected_product: dict[str, Any]) -> list[str]:
    attrs = selected_product.get("attributes") if isinstance(selected_product.get("attributes"), dict) else {}
    metadata = selected_product.get("metadata") if isinstance(selected_product.get("metadata"), dict) else {}
    raw_values = [
        selected_product.get("article_number"),
        selected_product.get("articleNumber"),
        selected_product.get("sku"),
        selected_product.get("id"),
        attrs.get("article_number"),
        attrs.get("articlenumber"),
        attrs.get("theben_article_number"),
        metadata.get("article_number"),
        metadata.get("legacy_article_number"),
    ]
    candidates = []
    for raw in raw_values:
        value = str(raw or "").strip()
        if value and value not in candidates:
            candidates.append(value)
    return candidates


def select_requested_products(products: list[dict[str, Any]], selected_product: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not selected_product:
        return select_demo_products(products)
    normalized = [normalize_product(p) for p in products]
    candidates = selected_article_candidates(selected_product)
    for candidate in candidates:
        candidate_slug = slug(candidate)
        for product in normalized:
            if candidate == product["article_number"] or candidate_slug == slug(product["article_number"]):
                return [product]
    if candidates:
        return [
            {
                "article_number": candidates[0],
                "name": selected_product.get("name") or candidates[0],
                "category": selected_product.get("family") or selected_product.get("category") or "Selected product",
                "source_system": "product-layer-selected-product",
                "source_base_url": os.environ.get("THEBEN_LEGACY_BASE_URL", "http://192.168.8.200:8000"),
            }
        ]
    raise ValueError("selected_product must contain sku, id, or article_number")


def collect_report_data(client: LegacyClient) -> dict[str, Any]:
    discovery = client.discover()
    selected = select_demo_products(client.list_products())
    products = []
    for product in selected:
        article = product["article_number"]
        bom = client.bom(article)
        certificate = client.certificate(article)
        sbom_payload = client.sbom(article)
        vulnerability_payload = client.vulnerabilities(article)
        sbom = build_cyclonedx(product, bom, sbom_payload)
        vex = build_vex(product, sbom, vulnerability_payload)
        products.append({
            "product": product,
            "bom": bom,
            "certificate": certificate,
            "sbom": sbom,
            "vex": vex,
            "vulnerability_count": len(vex["vulnerabilities"]),
        })
    return {
        "report_id": f"theben-report-{int(time.time())}",
        "generated_at": utc_now(),
        "legacy_base_url": client.base_url,
        "brand": brand_metadata(),
        "discovery": discovery,
        "products": products,
    }


def collect_security_export_data(
    client: LegacyClient,
    selected_product: dict[str, Any] | None = None,
    artifact_type: str = "both",
) -> dict[str, Any]:
    discovery = client.discover()
    selected = select_requested_products(client.list_products(), selected_product)
    products = []
    for product in selected:
        article = product["article_number"]
        evidence_warnings = []
        try:
            bom = client.bom(article)
        except Exception as exc:
            logger.warning("security export BOM unavailable for %s, continuing with empty BOM: %s", article, exc)
            bom = {"articleNumber": article, "bom": []}
            evidence_warnings.append({"type": "bom", "message": str(exc)})
        try:
            sbom_payload = client.sbom(article)
        except Exception as exc:
            logger.warning("security export SBOM unavailable for %s, continuing with BOM-derived SBOM: %s", article, exc)
            sbom_payload = None
            evidence_warnings.append({"type": "sbom", "message": str(exc)})
        try:
            vulnerability_payload = client.vulnerabilities(article)
        except Exception as exc:
            logger.warning("security export vulnerability data unavailable for %s, continuing with no CVEs: %s", article, exc)
            vulnerability_payload = []
            evidence_warnings.append({"type": "vulnerabilities", "message": str(exc)})
        sbom = build_cyclonedx(product, bom, sbom_payload)
        cve = build_cve_export(product, sbom, vulnerability_payload)
        openvex = build_openvex(product, sbom, vulnerability_payload)
        item = {
            "product": product,
            "sbom": sbom,
            "cve": cve,
            "openvex": openvex,
            "vulnerability_count": len(cve["cves"]),
            "evidence_warnings": evidence_warnings,
        }
        if artifact_type in {"both", "cve"}:
            item["cve_export"] = cve
        if artifact_type in {"both", "vex"}:
            item["vex_export"] = openvex
        products.append(item)
    return {
        "export_id": f"theben-security-export-{int(time.time())}",
        "artifact_type": artifact_type,
        "generated_at": utc_now(),
        "legacy_base_url": client.base_url,
        "brand": brand_metadata(),
        "discovery": discovery,
        "products": products,
    }


def brand_metadata() -> dict[str, Any]:
    return {
        "logo_path": str(LOGO_PATH),
        "logo_source": "user-provided attachment copied from 99_shared/logo_theben.jpg",
        "logo_sha256": file_sha256(LOGO_PATH),
        "primary_color": "#00456f",
        "accent_color": "#2f7d32",
        "usage": "Thebenpaul competition prototype PDF",
    }


def save_report_artifacts(report: dict[str, Any]) -> dict[str, Any]:
    report_id = report["report_id"]
    report_path = REPORT_DIR / f"{report_id}.json"
    html_path = REPORT_DIR / f"{report_id}.html"
    pdf_path = REPORT_DIR / f"{report_id}.pdf"
    write_json(report_path, report)
    for item in report["products"]:
        article_slug = slug(item["product"]["article_number"])
        write_json(SBOM_DIR / f"{article_slug}.cyclonedx.json", item["sbom"])
        write_json(VEX_DIR / f"{article_slug}.vex.json", item["vex"])
    html_path.write_text(render_html(report), encoding="utf-8")
    generate_pdf(report, pdf_path)
    return {
        "report_id": report_id,
        "json_path": str(report_path),
        "html_path": str(html_path),
        "pdf_path": str(pdf_path),
        "sbom_dir": str(SBOM_DIR),
        "vex_dir": str(VEX_DIR),
    }


def save_security_export_artifacts(export: dict[str, Any]) -> dict[str, Any]:
    artifact_type = export.get("artifact_type") or "both"
    written: dict[str, list[str]] = {"cve_paths": [], "openvex_paths": [], "sbom_paths": []}
    for item in export["products"]:
        article_slug = slug(item["product"]["article_number"])
        write_json(SBOM_DIR / f"{article_slug}.cyclonedx.json", item["sbom"])
        written["sbom_paths"].append(str(SBOM_DIR / f"{article_slug}.cyclonedx.json"))
        if artifact_type in {"both", "cve"}:
            cve_path = CVE_DIR / f"{article_slug}.cve.json"
            write_json(cve_path, item["cve"])
            written["cve_paths"].append(str(cve_path))
        if artifact_type in {"both", "vex"}:
            openvex_path = VEX_DIR / f"{article_slug}.openvex.json"
            write_json(openvex_path, item["openvex"])
            written["openvex_paths"].append(str(openvex_path))
    return {
        "export_id": export["export_id"],
        "artifact_type": artifact_type,
        **written,
        "sbom_dir": str(SBOM_DIR),
        "cve_dir": str(CVE_DIR),
        "vex_dir": str(VEX_DIR),
    }


def render_html(report: dict[str, Any]) -> str:
    product_sections = []
    for item in report["products"]:
        product = item["product"]
        cert = item["certificate"]
        bom_items = item["bom"].get("bom", [])
        product_sections.append(f"""
        <section>
          <h2>{html.escape(product['name'])}</h2>
          <p><strong>Article:</strong> {html.escape(product['article_number'])} · <strong>Category:</strong> {html.escape(product['category'])}</p>
          <h3>BOM Highlights</h3>
          <ul>{''.join(f"<li>{html.escape(str(row.get('partNumber', '')))} - {html.escape(str(row.get('description', '')))} ({html.escape(str(row.get('supplier', 'unknown')))})</li>" for row in bom_items[:6])}</ul>
          <h3>Certificate</h3>
          <p>{html.escape(str(cert.get('certificateType', 'Unknown')))} · {html.escape(str(cert.get('certificateId', 'n/a')))} · valid until {html.escape(str(cert.get('validUntil', 'n/a')))}</p>
          <h3>SBOM / VEX</h3>
          <p>{len(item['sbom'].get('components', []))} components · {item['vulnerability_count']} vulnerability finding(s)</p>
        </section>
        """)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Theben Compliance Overview</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 42px; color: #172033; }}
    header {{ border-bottom: 4px solid #00456f; padding-bottom: 18px; margin-bottom: 28px; }}
    img.logo {{ width: 220px; height: auto; }}
    h1 {{ color: #00456f; font-size: 30px; }}
    h2 {{ color: #00456f; border-bottom: 1px solid #d8e1ea; padding-bottom: 6px; }}
    h3 {{ color: #2f7d32; }}
    section {{ margin-bottom: 30px; }}
    .meta {{ color: #5f6f82; font-size: 13px; }}
  </style>
</head>
<body>
  <header>
    <img class="logo" src="/assets/logo_theben.jpg" alt="Theben logo">
    <h1>Compliance Overview - Vacuum Cleaner & Coffee Machine</h1>
    <p class="meta">Generated {html.escape(report['generated_at'])} · Prototype report · Source {html.escape(report['legacy_base_url'])}</p>
  </header>
  {''.join(product_sections)}
  <footer class="meta">Logo source: {html.escape(report['brand']['logo_source'])}. Advisory prototype output; human compliance sign-off remains required.</footer>
</body>
</html>
"""


def generate_pdf(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if SimpleDocTemplate is None:
        output_path.write_bytes(simple_pdf_bytes(report))
        return
    doc = SimpleDocTemplate(str(output_path), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ThebenTitle", parent=styles["Title"], textColor=colors.HexColor("#00456f"), fontSize=24, leading=30))
    styles.add(ParagraphStyle(name="ThebenHeading", parent=styles["Heading2"], textColor=colors.HexColor("#00456f"), spaceBefore=16))
    styles.add(ParagraphStyle(name="SmallMuted", parent=styles["Normal"], textColor=colors.HexColor("#5f6f82"), fontSize=8, leading=10))
    story: list[Any] = []
    if LOGO_PATH.exists():
        logo = Image(str(LOGO_PATH), width=70 * mm, height=23 * mm)
        story.append(logo)
        story.append(Spacer(1, 8 * mm))
    story.append(Paragraph("Compliance Overview - Vacuum Cleaner & Coffee Machine", styles["ThebenTitle"]))
    story.append(Paragraph(f"Generated {report['generated_at']} · Thebenpaul prototype", styles["SmallMuted"]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("Executive Summary", styles["ThebenHeading"]))
    story.append(Paragraph("This report connects proprietary REST product data with BOM, certificate, SBOM, CVE, and VEX evidence. It is formatted for Theben-style stakeholder review and remains advisory until human compliance sign-off.", styles["BodyText"]))
    for item in report["products"]:
        product = item["product"]
        cert = item["certificate"]
        story.append(PageBreak())
        story.append(Paragraph(product["name"], styles["ThebenTitle"]))
        rows = [
            ["Article number", product["article_number"]],
            ["Category", product["category"]],
            ["Certificate", f"{cert.get('certificateType', 'Unknown')} · {cert.get('certificateId', 'n/a')}"],
            ["Validity", f"{cert.get('issueDate', 'n/a')} to {cert.get('validUntil', 'n/a')}"],
            ["SBOM components", str(len(item["sbom"].get("components", [])))],
            ["VEX findings", str(item["vulnerability_count"])],
        ]
        table = Table(rows, colWidths=[42 * mm, 112 * mm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e8f0f6")),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#00456f")),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#b9c6d2")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (1, 0), (1, -1), [colors.white, colors.HexColor("#f7fafc")]),
        ]))
        story.append(table)
        story.append(Paragraph("BOM Highlights", styles["ThebenHeading"]))
        bom_rows = [["Part", "Description", "Qty", "Supplier"]]
        for row in item["bom"].get("bom", [])[:8]:
            bom_rows.append([
                str(row.get("partNumber", "")),
                str(row.get("description", "")),
                str(row.get("quantity", "")),
                str(row.get("supplier", "")),
            ])
        bom_table = Table(bom_rows, colWidths=[32 * mm, 64 * mm, 16 * mm, 42 * mm])
        bom_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#00456f")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#b9c6d2")),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
        ]))
        story.append(bom_table)
    story.append(PageBreak())
    story.append(Paragraph("Lineage and Brand Provenance", styles["ThebenHeading"]))
    story.append(Paragraph(f"Legacy REST source: {report['legacy_base_url']}", styles["BodyText"]))
    story.append(Paragraph(f"Logo source: {report['brand']['logo_source']}", styles["BodyText"]))
    story.append(Paragraph(f"Logo SHA-256: {report['brand']['logo_sha256']}", styles["SmallMuted"]))
    doc.build(story)


def ensure_pdf(report_id: str) -> Path:
    pdf_path = REPORT_DIR / f"{report_id}.pdf"
    report_path = REPORT_DIR / f"{report_id}.json"
    if not pdf_path.exists() or pdf_path.stat().st_size < 1_200:
        report = read_json(report_path)
        generate_pdf(report, pdf_path)
    return pdf_path


def simple_pdf_bytes(report: dict[str, Any]) -> bytes:
    lines = fallback_pdf_lines(report)
    stream_lines = [
        "BT",
        "/F1 11 Tf",
        "50 792 Td",
        "14 TL",
    ]
    for line in lines[:52]:
        stream_lines.append(f"({pdf_escape(line)}) Tj")
        stream_lines.append("T*")
    stream_lines.append("ET")
    stream = "\n".join(stream_lines)
    objects = [
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
        "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj",
        "4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
        f"5 0 obj << /Length {len(stream.encode('utf-8'))} >> stream\n{stream}\nendstream endobj",
    ]
    body = "%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(body.encode("utf-8")))
        body += obj + "\n"
    xref_pos = len(body.encode("utf-8"))
    body += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    body += "".join(f"{offset:010d} 00000 n \n" for offset in offsets[1:])
    body += f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n"
    return body.encode("utf-8")


def fallback_pdf_lines(report: dict[str, Any]) -> list[str]:
    lines = [
        "Theben Compliance Overview",
        f"Generated {report['generated_at']}",
        f"Source {report['legacy_base_url']}",
        f"Logo source: {report['brand']['logo_source']}",
        "",
        "Executive Summary",
        "Prototype compliance report with product identity, BOM highlights, SBOM, CVE and VEX overview.",
        "Advisory output only; human compliance sign-off remains required.",
        "",
    ]
    for item in report["products"]:
        product = item["product"]
        cert = item["certificate"]
        lines.append(f"{product['article_number']} - {product['name']}")
        lines.append(f"Category: {product['category']}")
        lines.append(f"Certificate: {cert.get('certificateType', 'Unknown')} / {cert.get('certificateId', 'n/a')}")
        lines.append(f"Validity: {cert.get('issueDate', 'n/a')} to {cert.get('validUntil', 'n/a')}")
        lines.append(f"SBOM components: {len(item['sbom'].get('components', []))}; VEX findings: {item['vulnerability_count']}")
        lines.append("BOM highlights:")
        for row in item["bom"].get("bom", [])[:8]:
            lines.append(
                f"- {row.get('partNumber', '')}: {row.get('description', '')} "
                f"x{row.get('quantity', '')} / {row.get('supplier', row.get('manufacturerName', 'unknown'))}"
            )
        if item["vex"].get("vulnerabilities"):
            lines.append("VEX findings:")
            for vuln in item["vex"]["vulnerabilities"][:6]:
                status = ", ".join(vuln.get("product_status", {}).keys()) or "unknown"
                lines.append(f"- {vuln.get('cve', 'UNKNOWN-CVE')} / {vuln.get('severity', 'unknown')} / {status}")
        lines.append("")
    wrapped = []
    for line in lines:
        wrapped.extend(wrap_pdf_line(str(line), 92))
    return wrapped


def wrap_pdf_line(line: str, width: int) -> list[str]:
    cleaned = line.encode("latin-1", "replace").decode("latin-1")
    if len(cleaned) <= width:
        return [cleaned]
    parts = []
    current = cleaned
    while len(current) > width:
        cut = current.rfind(" ", 0, width)
        if cut <= 0:
            cut = width
        parts.append(current[:cut])
        current = "  " + current[cut:].strip()
    if current:
        parts.append(current)
    return parts


def pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def fallback_enabled(config: dict[str, Any]) -> bool:
    return os.environ.get(
        "THEBEN_USE_FIXTURES",
        str(config.get("use_fixtures_when_unreachable", True)),
    ).lower() in {"1", "true", "yes"}


def create_report(use_fixture: bool | None = None, force_live_only: bool = False) -> dict[str, Any]:
    config = load_config()
    base_url = os.environ.get("THEBEN_LEGACY_BASE_URL", config.get("legacy_base_url", "http://192.168.8.200:8000"))
    timeout = float(os.environ.get("THEBEN_LEGACY_TIMEOUT", config.get("legacy_timeout_seconds", 5)))
    if use_fixture is True:
        fixture_client = LegacyClient(base_url, timeout=timeout, use_fixture=True)
        report = collect_report_data(fixture_client)
        report["fixture_fallback"] = True
        artifacts = save_report_artifacts(report)
        return {"status": "ok", "artifacts": artifacts, "report": report}
    allow_fallback = not force_live_only and fallback_enabled(config)
    client = LegacyClient(base_url, timeout=timeout, use_fixture=False)
    try:
        report = collect_report_data(client)
    except Exception as exc:
        if not allow_fallback:
            raise
        logger.warning("legacy system unavailable, using fixtures: %s", exc)
        fixture_client = LegacyClient(base_url, timeout=timeout, use_fixture=True)
        report = collect_report_data(fixture_client)
        report["fixture_fallback"] = True
        report["legacy_error"] = str(exc)
    artifacts = save_report_artifacts(report)
    return {"status": "ok", "artifacts": artifacts, "report": report}


def create_security_export(
    *,
    selected_product: dict[str, Any] | None = None,
    artifact_type: str = "both",
    use_fixture: bool | None = None,
    force_live_only: bool = False,
) -> dict[str, Any]:
    artifact_type = str(artifact_type or "both").strip().lower()
    if artifact_type not in {"both", "cve", "vex"}:
        raise ValueError("artifact_type must be one of: both, cve, vex")
    config = load_config()
    base_url = os.environ.get("THEBEN_LEGACY_BASE_URL", config.get("legacy_base_url", "http://192.168.8.200:8000"))
    timeout = float(os.environ.get("THEBEN_LEGACY_TIMEOUT", config.get("legacy_timeout_seconds", 5)))
    if use_fixture is True:
        fixture_client = LegacyClient(base_url, timeout=timeout, use_fixture=True)
        export = collect_security_export_data(fixture_client, selected_product, artifact_type)
        export["fixture_fallback"] = True
        artifacts = save_security_export_artifacts(export)
        return {"status": "ok", "artifacts": artifacts, "export": export}
    allow_fallback = not force_live_only and fallback_enabled(config)
    client = LegacyClient(base_url, timeout=timeout, use_fixture=False)
    try:
        export = collect_security_export_data(client, selected_product, artifact_type)
    except Exception as exc:
        if not allow_fallback:
            raise
        logger.warning("legacy security export unavailable, using fixtures: %s", exc)
        fixture_client = LegacyClient(base_url, timeout=timeout, use_fixture=True)
        export = collect_security_export_data(fixture_client, selected_product, artifact_type)
        export["fixture_fallback"] = True
        export["legacy_error"] = str(exc)
    artifacts = save_security_export_artifacts(export)
    return {"status": "ok", "artifacts": artifacts, "export": export}


class ThebenHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        logger.info("%s - %s", self.client_address[0], format % args)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        try:
            if path == "/":
                self.send_html(render_landing_page())
            elif path == "/favicon.ico":
                self.send_empty(HTTPStatus.NO_CONTENT)
            elif path == "/assets/logo_theben.jpg":
                self.send_file(LOGO_PATH, "image/jpeg")
            elif path == "/health":
                self.send_json({"status": "ok", "service": "theben-layer", "brand": brand_metadata()})
            elif path == "/api/theben/reports":
                self.send_json({"reports": list_reports()})
            elif path == "/api/theben/sbom":
                self.send_json(list_security_artifacts())
            elif path == "/api/theben/cve":
                self.send_json({"cve_artifacts": list_artifacts(CVE_DIR, "/api/theben/cve"), "generated_at": utc_now()})
            elif path.startswith("/api/theben/cve/"):
                filename = unquote(path.removeprefix("/api/theben/cve/"))
                self.send_artifact(CVE_DIR, filename)
            elif path.startswith("/api/theben/sbom/"):
                filename = unquote(path.removeprefix("/api/theben/sbom/"))
                self.send_artifact(SBOM_DIR, filename)
            elif path == "/api/theben/vex":
                self.send_json(
                    {
                        "vex_artifacts": list_artifacts(VEX_DIR, "/api/theben/vex"),
                        "openvex_artifacts": list_artifacts(VEX_DIR, "/api/theben/vex", ".openvex.json"),
                        "generated_at": utc_now(),
                    }
                )
            elif path.startswith("/api/theben/vex/"):
                filename = unquote(path.removeprefix("/api/theben/vex/"))
                self.send_artifact(VEX_DIR, filename)
            elif path == "/api/theben/products":
                config = load_config()
                base_url = os.environ.get("THEBEN_LEGACY_BASE_URL", config.get("legacy_base_url", "http://192.168.8.200:8000"))
                client = LegacyClient(base_url, timeout=float(config.get("legacy_timeout_seconds", 5)), use_fixture=False)
                fixture_fallback = False
                try:
                    rows = client.list_products()
                except Exception as exc:
                    logger.warning("legacy products unavailable, using fixtures: %s", exc)
                    rows = LegacyClient(base_url, use_fixture=True).list_products()
                    fixture_fallback = True
                self.send_json({
                    "source": base_url,
                    "fixture_fallback": fixture_fallback,
                    "products": [normalize_product(p) for p in rows],
                })
            elif path.startswith("/api/theben/reports/") and path.endswith("/pdf"):
                report_id = unquote(path.split("/")[-2])
                self.send_file(ensure_pdf(report_id), PDF_MIME)
            elif path.startswith("/api/theben/reports/") and path.endswith("/preview"):
                report_id = unquote(path.split("/")[-2])
                self.send_file(REPORT_DIR / f"{report_id}.html", HTML_MIME)
            elif path.startswith("/api/theben/reports/"):
                report_id = unquote(path.rsplit("/", 1)[-1])
                self.send_json(read_json(REPORT_DIR / f"{report_id}.json"))
            else:
                self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except FileNotFoundError:
            self.send_json({"error": "report not found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            logger.exception("GET failed: %s", exc)
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        try:
            if path in {"/api/theben/reports", "/api/theben/extract"}:
                body = self.read_json(optional=True)
                result = create_report(
                    use_fixture=body.get("use_fixtures"),
                    force_live_only=bool(body.get("force_live_only", False)),
                )
                self.send_json(result, HTTPStatus.CREATED)
            elif path == "/api/theben/security-export":
                body = self.read_json(optional=True)
                result = create_security_export(
                    selected_product=body.get("selected_product") if isinstance(body.get("selected_product"), dict) else None,
                    artifact_type=body.get("artifact_type", "both"),
                    use_fixture=body.get("use_fixtures"),
                    force_live_only=bool(body.get("force_live_only", False)),
                )
                self.send_json(result, HTTPStatus.CREATED)
            else:
                self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            logger.warning("POST validation failed: %s", exc)
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            logger.warning("POST upstream failed: %s", exc)
            self.send_json(
                {
                    "error": f"legacy Theben REST system unavailable: {exc}",
                    "fallback_hint": "leave force_live_only unset or set use_fixtures=true to allow configured fixture fallback",
                },
                HTTPStatus.BAD_GATEWAY,
            )

    def read_json(self, optional: bool = False) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {} if optional else {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", JSON_MIME)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def send_html(self, html_body: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = html_body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", HTML_MIME)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def send_empty(self, status: HTTPStatus) -> None:
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def send_file(self, path: Path, mime: str) -> None:
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_artifact(self, root: Path, filename: str) -> None:
        safe_name = Path(filename).name
        if safe_name != filename or not safe_name.endswith(".json"):
            self.send_json({"error": "artifact not found"}, HTTPStatus.NOT_FOUND)
            return
        self.send_file(root / safe_name, JSON_MIME)


def list_reports() -> list[dict[str, Any]]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    reports = []
    for path in sorted(REPORT_DIR.glob("*.json"), reverse=True):
        try:
            payload = read_json(path)
        except Exception:
            continue
        report_id = payload.get("report_id") or path.stem
        reports.append({
            "report_id": report_id,
            "generated_at": payload.get("generated_at"),
            "product_count": len(payload.get("products", [])),
            "fixture_fallback": bool(payload.get("fixture_fallback")),
            "json_url": f"/api/theben/reports/{report_id}",
            "pdf_url": f"/api/theben/reports/{report_id}/pdf",
            "preview_url": f"/api/theben/reports/{report_id}/preview",
        })
    return reports


def list_security_artifacts() -> dict[str, Any]:
    SBOM_DIR.mkdir(parents=True, exist_ok=True)
    CVE_DIR.mkdir(parents=True, exist_ok=True)
    VEX_DIR.mkdir(parents=True, exist_ok=True)
    return {
        "sbom_artifacts": list_artifacts(SBOM_DIR, "/api/theben/sbom"),
        "cve_artifacts": list_artifacts(CVE_DIR, "/api/theben/cve"),
        "vex_artifacts": list_artifacts(VEX_DIR, "/api/theben/vex"),
        "openvex_artifacts": list_artifacts(VEX_DIR, "/api/theben/vex", ".openvex.json"),
        "generated_at": utc_now(),
    }


def list_artifacts(directory: Path, url_prefix: str, suffix: str = ".json") -> list[dict[str, Any]]:
    artifacts = []
    for path in sorted(directory.glob(f"*{suffix}")):
        artifacts.append(
            {
                "filename": path.name,
                "url": f"{url_prefix}/{quote(path.name)}",
                "size_bytes": path.stat().st_size,
                "sha256": file_sha256(path),
                "updated_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat(),
            }
        )
    return artifacts


def render_landing_page() -> str:
    reports = list_reports()
    latest = reports[0] if reports else None
    report_links = ""
    if latest:
        report_links = f"""
          <a class="button" href="{html.escape(latest['preview_url'])}">Open latest preview</a>
          <a class="button secondary" href="{html.escape(latest['pdf_url'])}">Download latest PDF</a>
        """
    rows = "".join(
        f"""
        <tr>
          <td>{html.escape(str(report.get('report_id')))}</td>
          <td>{html.escape(str(report.get('generated_at') or ''))}</td>
          <td>{html.escape(str(report.get('product_count')))}</td>
          <td><a href="{html.escape(report['preview_url'])}">Preview</a> · <a href="{html.escape(report['pdf_url'])}">PDF</a></td>
        </tr>
        """
        for report in reports[:10]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Theben Layer</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; background: #f6f8fb; color: #182230; }}
    header {{ background: #ffffff; border-bottom: 4px solid #00456f; padding: 28px 36px; }}
    main {{ max-width: 980px; margin: 0 auto; padding: 32px 24px; }}
    img {{ width: 220px; max-width: 70vw; height: auto; }}
    h1 {{ color: #00456f; margin: 20px 0 6px; }}
    .panel {{ background: #ffffff; border: 1px solid #d9e2ec; border-radius: 8px; padding: 22px; margin-bottom: 22px; }}
    .button {{ display: inline-block; background: #00456f; color: white; text-decoration: none; padding: 10px 14px; border-radius: 6px; font-weight: 700; margin: 8px 8px 0 0; }}
    .button.secondary {{ background: #2f7d32; }}
    code {{ background: #eef3f8; padding: 2px 5px; border-radius: 4px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ text-align: left; border-bottom: 1px solid #e4ebf2; padding: 9px; }}
  </style>
</head>
<body>
  <header>
    <img src="/assets/logo_theben.jpg" alt="Theben logo">
    <h1>Theben Layer</h1>
    <p>Theben-styled competition reports, SBOM, CVE and VEX outputs.</p>
  </header>
  <main>
    <section class="panel">
      <h2>Status</h2>
      <p>Service is running. Health endpoint: <code>/health</code>.</p>
      <p>Create a report with:</p>
      <p><code>curl -X POST http://localhost:8098/api/theben/reports -H "Content-Type: application/json" -d '{{"use_fixtures":true}}'</code></p>
      {report_links}
    </section>
    <section class="panel">
      <h2>Recent Reports</h2>
      <table>
        <thead><tr><th>ID</th><th>Generated</th><th>Products</th><th>Links</th></tr></thead>
        <tbody>{rows or '<tr><td colspan="4">No reports generated yet.</td></tr>'}</tbody>
      </table>
    </section>
  </main>
</body>
</html>"""


def run_server(host: str, port: int) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    SBOM_DIR.mkdir(parents=True, exist_ok=True)
    CVE_DIR.mkdir(parents=True, exist_ok=True)
    VEX_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((host, port), ThebenHandler)
    logger.info("theben-layer listening on http://%s:%s", host, port)
    server.serve_forever()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Theben corporate identity layer")
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8098")))
    parser.add_argument("--generate-report", action="store_true")
    parser.add_argument("--fixtures", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.generate_report:
        result = create_report(use_fixture=args.fixtures)
        print(json.dumps(result["artifacts"], indent=2, sort_keys=True))
        return 0
    run_server(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
