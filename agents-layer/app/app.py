#!/usr/bin/env python3
"""Lightweight advisory agents layer for Thebenpaul.

The service intentionally stays small and dependency-free for the first
implementation wave. It reads editable configuration from ``config/`` and
returns deterministic advisory assessments with traceability. Product data
ownership remains in product-layer; evidence ownership remains in data-layer.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = Path(os.getenv("THEBEN_AGENTS_DATA_DIR", str(BASE_DIR / "data")))
ASSESSMENTS_FILE = DATA_DIR / "assessments.json"
JSON = "application/json; charset=utf-8"
HTML = "text/html; charset=utf-8"
TEXT = "text/plain; charset=utf-8"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path, default: Any) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return default


def load_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def config_payload() -> dict[str, Any]:
    return {
        "runtime": load_json(CONFIG_DIR / "runtime.json", {}),
        "rule_catalog": load_json(CONFIG_DIR / "rule_catalog.json", {}),
        "evidence_model": load_json(CONFIG_DIR / "evidence_model.json", {}),
        "access_control": load_json(CONFIG_DIR / "access_control.json", {}),
        "ai_agents": load_text(CONFIG_DIR / "ai_agents.md"),
        "standards_validity": load_text(CONFIG_DIR / "standards_validity.md"),
    }


def list_skill_files() -> list[str]:
    return sorted(path.name for path in CONFIG_DIR.glob("*_skill.md")) + sorted(
        path.name for path in CONFIG_DIR.glob("expert_*.md")
    )


def standards_records(markdown: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    lines = [line.strip() for line in markdown.splitlines() if line.strip().startswith("|")]
    table_lines = [line for line in lines if not re.match(r"^\|[- :|]+\|$", line)]
    if len(table_lines) < 2:
        return records
    headers = [cell.strip().lower().replace(" ", "_") for cell in table_lines[0].strip("|").split("|")]
    for line in table_lines[1:]:
        values = [cell.strip() for cell in line.strip("|").split("|")]
        if len(values) == len(headers):
            records.append(dict(zip(headers, values)))
    return records


def all_agents(config: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    catalog = config["rule_catalog"]
    compliance = catalog.get("compliance_agents", [])
    expert = catalog.get("expert_agents", [])
    return {
        "compliance-agents-layer": compliance,
        "expert-agents-layer": expert,
    }


def enabled_agent_ids(config: dict[str, Any]) -> set[str]:
    runtime = config["runtime"]
    enabled = runtime.get("enabled_agents", {})
    ids: set[str] = set()
    for layer in ("compliance", "expert"):
        configured = enabled.get(layer)
        if isinstance(configured, list):
            ids.update(str(item) for item in configured)
    if ids:
        return ids
    for layer_agents in all_agents(config).values():
        ids.update(str(agent["id"]) for agent in layer_agents if agent.get("enabled", True))
    return ids


def requested_agent_ids(body: dict[str, Any]) -> set[str]:
    raw = body.get("agent_ids") or body.get("requested_agent_ids") or []
    if not isinstance(raw, list):
        return set()
    return {str(item).strip() for item in raw if str(item).strip()}


def role_from_headers(headers: Any) -> str:
    default_role = str(os.getenv("THEBEN_DEFAULT_ROLE") or "viewer").strip().lower()
    requested_role = str(headers.get("X-Role") or default_role).strip().lower()
    role_token = (os.getenv("THEBEN_AGENTS_ROLE_TOKEN") or os.getenv("THEBEN_ROLE_TOKEN") or "").strip()
    provided_token = str(headers.get("X-Role-Token") or "").strip()
    auth_header = str(headers.get("Authorization") or "").strip()
    if auth_header.lower().startswith("bearer "):
        provided_token = auth_header[7:].strip()
    trust_headers = str(os.getenv("THEBEN_AGENTS_TRUST_ROLE_HEADERS") or "").strip().lower() in {"1", "true", "yes", "on"}
    if role_token:
        return requested_role if provided_token == role_token else default_role
    return requested_role if trust_headers else default_role


def permissions_for_role(config: dict[str, Any], role: str) -> set[str]:
    roles = config["access_control"].get("roles", {})
    perms = roles.get(role, roles.get("viewer", {})).get("permissions", [])
    return set(str(item) for item in perms)


def can(role_permissions: set[str], permission: str) -> bool:
    return "*" in role_permissions or permission in role_permissions


def field_value(product: dict[str, Any], dotted: str) -> Any:
    current: Any = product
    for part in dotted.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def evidence_by_type(evidence: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in evidence:
        kind = str(item.get("type") or "unknown")
        grouped.setdefault(kind, []).append(item)
    return grouped


def agent_by_id(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for agents in all_agents(config).values():
        for agent in agents:
            result[str(agent["id"])] = agent
    return result


def assess_product(body: dict[str, Any], role: str = "viewer") -> dict[str, Any]:
    config = config_payload()
    permissions = permissions_for_role(config, role)
    if not can(permissions, "assessment:run"):
        raise PermissionError(f"role {role!r} cannot run assessments")

    product = body.get("product") if isinstance(body.get("product"), dict) else {}
    evidence = body.get("evidence") if isinstance(body.get("evidence"), list) else []
    target_market = str(body.get("target_market") or product.get("target_market") or "EU")
    date_on_market = str(body.get("date_placing_on_market") or product.get("date_placing_on_market") or "")
    product_id = str(product.get("id") or product.get("sku") or body.get("product_id") or "unknown-product")
    product_family = str(product.get("family") or product.get("product_family") or "unknown-family")
    enabled_ids = enabled_agent_ids(config)
    requested_ids = requested_agent_ids(body)
    if requested_ids:
        enabled_ids = enabled_ids & requested_ids
    grouped_evidence = evidence_by_type(evidence)
    agents = agent_by_id(config)
    rules = [
        rule
        for rule in config["rule_catalog"].get("rules", [])
        if str(rule.get("agent_id")) in enabled_ids
    ]

    findings: list[dict[str, Any]] = []
    for rule in rules:
        agent_id = str(rule["agent_id"])
        missing_product_fields = [
            field for field in rule.get("required_product_fields", []) if field_value(product, str(field)) in (None, "")
        ]
        missing_evidence = [
            kind for kind in rule.get("required_evidence_types", []) if not grouped_evidence.get(str(kind))
        ]
        failed = bool(missing_product_fields or missing_evidence)
        severity = str(rule.get("severity") or "medium")
        status = "needs_review" if failed else "passed"
        evidence_refs = []
        for kind in rule.get("required_evidence_types", []):
            for item in grouped_evidence.get(str(kind), []):
                evidence_refs.append(
                    {
                        "type": kind,
                        "reference": item.get("reference") or item.get("id") or "unreferenced",
                        "source_layer": item.get("source_layer") or "data-layer",
                        "confidence": item.get("confidence", "unknown"),
                    }
                )
        findings.append(
            {
                "finding_id": f"finding-{uuid.uuid4().hex[:12]}",
                "agent_id": agent_id,
                "agent_name": agents.get(agent_id, {}).get("name", agent_id),
                "layer": agents.get(agent_id, {}).get("layer", "unknown"),
                "rule_id": rule.get("id"),
                "rule_version": rule.get("version"),
                "criterion": rule.get("criterion"),
                "severity": severity,
                "status": status,
                "missing_product_fields": missing_product_fields,
                "missing_evidence": missing_evidence,
                "standard_refs": rule.get("standard_refs", []),
                "recommended_action": rule.get("recommended_action"),
                "traceability": {
                    "product_id": product_id,
                    "product_family": product_family,
                    "target_market": target_market,
                    "date_placing_on_market": date_on_market,
                    "source_layers": ["product-layer", "data-layer"],
                    "evidence_refs": evidence_refs,
                    "rule_ref": rule.get("id"),
                    "agent_version": agents.get(agent_id, {}).get("version", "0.1.0"),
                    "assessment_timestamp": utc_now(),
                    "human_review_state": "pending",
                },
                "assumptions": rule.get("assumptions", []),
            }
        )

    failed_count = sum(1 for item in findings if item["status"] != "passed")
    high_or_critical = sum(1 for item in findings if item["status"] != "passed" and item["severity"] in {"high", "critical"})
    readiness_score = max(0, 100 - failed_count * 10 - high_or_critical * 10)
    if high_or_critical:
        readiness_status = "blocked"
    elif failed_count:
        readiness_status = "review_required"
    else:
        readiness_status = "ready_for_human_review"

    assessment = {
        "assessment_id": f"assessment-{uuid.uuid4().hex[:12]}",
        "schema_version": "0.1.0",
        "created_at": utc_now(),
        "advisory_only": True,
        "human_signoff_required": True,
        "product_context": {
            "product_id": product_id,
            "product_family": product_family,
            "target_market": target_market,
            "date_placing_on_market": date_on_market,
            "lifecycle_state": product.get("lifecycle_state", "unknown"),
            "requested_agent_ids": sorted(requested_ids),
        },
        "readiness": {
            "status": readiness_status,
            "score": readiness_score,
            "failed_checks": failed_count,
            "blocking_or_high_risk_checks": high_or_critical,
        },
        "findings": findings,
        "workflow_feedback": {
            "product_layer_write_policy": "advisory output only; product master and DPP updates require human review",
            "data_layer_write_policy": "raw evidence is not mutated; missing evidence is routed as a finding",
            "mempalace_summary_ready": True,
        },
    }
    assessments = load_json(ASSESSMENTS_FILE, [])
    if isinstance(assessments, list):
        assessments.append(assessment)
        write_json(ASSESSMENTS_FILE, assessments[-100:])
    return assessment


def html_dashboard(config: dict[str, Any]) -> str:
    agents = all_agents(config)
    compliance_count = len(agents["compliance-agents-layer"])
    expert_count = len(agents["expert-agents-layer"])
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Thebenpaul Agents Layer</title>
  <style>
    :root {{
      --ink: #0f1117;
      --muted: #6b7280;
      --line: #e5e7eb;
      --soft: #f8fafc;
      --panel: #ffffff;
      --brand: #22c55e;
      --brand-hover: #16a34a;
      --ok: #16a34a;
      --warn: #d97706;
      --shadow: 0 10px 28px rgba(15, 17, 23, 0.07);
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      font-size: 14px;
      line-height: 1.45;
      color: var(--ink);
      background: #fff;
    }}

    .topbar {{
      display: flex;
      justify-content: space-between;
      gap: 24px;
      align-items: center;
      padding: 18px 28px;
      background: #fff;
      border-bottom: 1px solid var(--line);
    }}

    h1 {{
      margin: 0 0 6px;
      font-size: 20px;
      font-weight: 800;
    }}

    p {{
      margin: 0;
      color: var(--muted);
    }}

    nav {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}

    a {{
      color: var(--ink);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 7px 10px;
      text-decoration: none;
      font-size: 12px;
      font-weight: 700;
      background: var(--soft);
      transition: border-color 140ms ease, color 140ms ease;
    }}

    a:hover {{
      border-color: rgba(34, 197, 94, 0.45);
      color: var(--ok);
    }}

    main {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 24px;
    }}

    .grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }}

    .metric,
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }}

    .metric {{
      border-left: 3px solid var(--brand);
      padding: 14px;
    }}

    .metric strong {{
      display: block;
      font-size: 24px;
      font-weight: 800;
    }}

    .metric span {{
      color: var(--muted);
    }}

    .panel {{
      padding: 16px;
    }}

    h2 {{
      margin: 0 0 12px;
      font-size: 16px;
      font-weight: 800;
    }}

    .status-list {{
      display: grid;
      gap: 10px;
      padding: 0;
      margin: 0;
      list-style: none;
    }}

    .status-list li {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      border-bottom: 1px solid var(--line);
      padding: 8px 0;
    }}

    .status-list li:last-child {{
      border-bottom: 0;
    }}

    .badge {{
      display: inline-block;
      border-radius: 999px;
      padding: 3px 8px;
      background: rgba(22, 163, 74, 0.12);
      color: var(--ok);
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }}

    code {{
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--soft);
      padding: 2px 5px;
      font-size: 12px;
    }}

    @media (max-width: 800px) {{
      .topbar,
      .grid {{
        display: block;
      }}

      nav,
      .metric {{
        margin-top: 12px;
      }}
    }}
  </style>
</head>
<body>
  <header class="topbar">
    <div>
      <h1>Thebenpaul Agents Layer</h1>
      <p>Lightweight advisory runtime for compliance and expert agents.</p>
    </div>
    <nav>
      <a href="/api/agents">Agents JSON</a>
      <a href="/api/standards-validity">Standards validity JSON</a>
      <a href="/api/open-items">Open items JSON</a>
    </nav>
  </header>
  <main>
    <section class="grid">
      <div class="metric"><strong>{compliance_count}</strong><span>Compliance agents</span></div>
      <div class="metric"><strong>{expert_count}</strong><span>Expert agents</span></div>
      <div class="metric"><strong>{compliance_count + expert_count}</strong><span>Total advisory agents</span></div>
    </section>
    <section class="panel">
      <h2>Runtime guardrails</h2>
      <ul class="status-list">
        <li><span>Assessment mode</span><span class="badge">Advisory only</span></li>
        <li><span>Human validation</span><span class="badge">Required</span></li>
        <li><span>Source layers</span><span><code>product-layer</code> <code>data-layer</code></span></li>
      </ul>
    </section>
  </main>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "ThebenpaulAgentsLayer/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.log_date_time_string(), fmt % args))

    def send_body(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, payload: Any, status: int = 200) -> None:
        self.send_body(status, json.dumps(payload, indent=2, sort_keys=True).encode("utf-8"), JSON)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        config = config_payload()
        if path == "/":
            return self.send_body(200, html_dashboard(config).encode("utf-8"), HTML)
        if path == "/health":
            return self.send_json({"status": "ok", "service": "agents-layer", "time": utc_now()})
        if path == "/api/agents":
            return self.send_json({"layers": all_agents(config), "skill_files": list_skill_files()})
        if path == "/api/compliance-agents":
            return self.send_json({"agents": all_agents(config)["compliance-agents-layer"]})
        if path == "/api/expert-agents":
            return self.send_json({"agents": all_agents(config)["expert-agents-layer"]})
        if path == "/api/standards-validity":
            markdown = config["standards_validity"]
            return self.send_json({"markdown": markdown, "records": standards_records(markdown)})
        if path == "/api/integrations":
            runtime = config["runtime"]
            return self.send_json(
                {
                    "product_layer": runtime.get("product_layer", {}),
                    "data_layer": runtime.get("data_layer", {}),
                    "mempalace": runtime.get("mempalace", {}),
                    "llm": runtime.get("llm", {}),
                }
            )
        if path == "/api/open-items":
            return self.send_json({"open_items": []})
        if path == "/api/assessments":
            query = parse_qs(parsed.query)
            limit = int(query.get("limit", ["20"])[0])
            assessments = load_json(ASSESSMENTS_FILE, [])
            return self.send_json({"assessments": assessments[-limit:] if isinstance(assessments, list) else []})
        return self.send_json({"error": "not found", "path": path}, status=404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path == "/api/assessments":
            try:
                assessment = assess_product(self.read_json(), role_from_headers(self.headers))
                return self.send_json(assessment, status=201)
            except PermissionError as exc:
                return self.send_json({"error": str(exc)}, status=403)
            except json.JSONDecodeError as exc:
                return self.send_json({"error": f"invalid JSON: {exc}"}, status=400)
        return self.send_json({"error": "not found", "path": path}, status=404)


def run(host: str, port: int) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"agents-layer listening on http://{host}:{port}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Thebenpaul agents-layer service")
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8090")))
    args = parser.parse_args()
    run(args.host, args.port)


if __name__ == "__main__":
    main()
