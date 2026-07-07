#!/usr/bin/env python3
"""Dependency-free avatar-layer service for Thebenpaul assessment playback.

The avatar layer is intentionally thin: it transforms governed product-layer
and agents-layer assessment payloads into spoken/display summaries, transcript
metadata, and role-filtered traceability. It does not own product data,
evidence, findings, or certification decisions.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = BASE_DIR / "config"
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = Path(os.getenv("THEBEN_AVATAR_DATA_DIR", str(BASE_DIR / "data")))
AUDIT_FILE = DATA_DIR / "avatar_audit.jsonl"

JSON = "application/json; charset=utf-8"
HTML = "text/html; charset=utf-8"
TEXT = "text/plain; charset=utf-8"
JS = "application/javascript; charset=utf-8"
CSS = "text/css; charset=utf-8"

SEVERITY_RANK = {"none": 0, "info": 1, "low": 2, "medium": 3, "high": 4, "critical": 5}
STATUS_BY_SEVERITY = {
    "critical": "blocked",
    "high": "review_required",
    "medium": "review_required",
    "low": "attention",
    "info": "ready_for_review",
    "none": "ready_for_review",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path, default: Any) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return default


def config_payload() -> dict[str, Any]:
    return {
        "runtime": load_json(CONFIG_DIR / "runtime.json", {}),
        "avatar_profiles": load_json(CONFIG_DIR / "avatar_profiles.json", {}),
        "speech_policies": load_json(CONFIG_DIR / "speech_policies.json", {}),
        "assessment_modes": load_json(CONFIG_DIR / "assessment_modes.json", {}),
    }


def append_audit_events(events: list[dict[str, Any]]) -> None:
    if not events:
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with AUDIT_FILE.open("a", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, sort_keys=True) + "\n")


def role_from_headers(headers: Any) -> str:
    default_role = str(os.getenv("THEBEN_AVATAR_DEFAULT_ROLE") or "viewer").strip().lower()
    requested_role = str(headers.get("X-Role") or default_role).strip().lower()
    role_token = os.getenv("THEBEN_AVATAR_ROLE_TOKEN", "").strip()
    provided_token = str(headers.get("X-Role-Token") or "").strip()
    auth_header = str(headers.get("Authorization") or "").strip()
    if auth_header.lower().startswith("bearer "):
        provided_token = auth_header[7:].strip()
    trust_headers = str(os.getenv("THEBEN_AVATAR_TRUST_ROLE_HEADERS") or "").strip().lower() in {"1", "true", "yes", "on"}
    if role_token:
        return requested_role if provided_token == role_token else default_role
    return requested_role if trust_headers else default_role


def role_from_request(body: dict[str, Any], headers: Any | None = None) -> str:
    header_role = role_from_headers(headers or {})
    trust_body = str(os.getenv("THEBEN_AVATAR_TRUST_BODY_ROLE") or "").strip().lower() in {"1", "true", "yes", "on"}
    requested = str(body.get("role") or body.get("viewer_role") or header_role).strip().lower()
    return (requested if trust_body else header_role) or "viewer"


def compact_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def safe_text(value: Any, limit: int = 280) -> str:
    text = compact_spaces(str(value or ""))
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."


def as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def get_assessment_payload(body: dict[str, Any]) -> dict[str, Any]:
    for key in ("assessment", "assessment_payload", "precomputed_assessment", "agent_assessment"):
        value = body.get(key)
        if isinstance(value, dict):
            return value
    nested = body.get("payload")
    if isinstance(nested, dict):
        return nested
    return body if any(key in body for key in ("findings", "readiness", "evidence_refs")) else {}


def requested_agent_ids(body: dict[str, Any], assessment: dict[str, Any]) -> list[str]:
    ids = as_list(body.get("agent_ids") or body.get("requested_agent_ids"))
    if not ids:
        ids = as_list(assessment.get("agent_ids") or assessment.get("requested_agent_ids"))
    if not ids and isinstance(assessment.get("product_context"), dict):
        ids = as_list(assessment["product_context"].get("requested_agent_ids"))
    if not ids:
        ids = [
            str(item.get("agent_id"))
            for item in as_list(assessment.get("findings"))
            if isinstance(item, dict) and item.get("agent_id")
        ]
    return sorted({str(item).strip() for item in ids if str(item).strip()})


def product_id_from(body: dict[str, Any], assessment: dict[str, Any]) -> str:
    product = body.get("product") if isinstance(body.get("product"), dict) else {}
    context = assessment.get("product_context") if isinstance(assessment.get("product_context"), dict) else {}
    return str(
        body.get("product_id")
        or product.get("id")
        or product.get("sku")
        or context.get("product_id")
        or assessment.get("product_id")
        or "unknown-product"
    )


def product_context_from(body: dict[str, Any], product_id: str) -> dict[str, Any]:
    raw = body.get("product_context") if isinstance(body.get("product_context"), dict) else {}
    return {
        "id": raw.get("id") or product_id,
        "sku": raw.get("sku"),
        "name": raw.get("name"),
        "family": raw.get("family"),
        "lifecycle_state": raw.get("lifecycle_state") or raw.get("lifecycle_status") or "unknown",
        "classification": raw.get("classification") or "internal",
        "lakehouse_layer": raw.get("lakehouse_layer") or "curated",
    }


def assessment_mode(body: dict[str, Any], assessment: dict[str, Any], config: dict[str, Any]) -> str:
    configured = config["assessment_modes"].get("modes", {})
    raw = str(body.get("assessment_mode") or assessment.get("assessment_mode") or body.get("mode") or "general")
    if raw in configured:
        return raw
    if "cyber" in raw.lower():
        return "cybersecurity"
    if "dpp" in raw.lower() or "passport" in raw.lower():
        return "dpp"
    return "general"


def role_policy(config: dict[str, Any], role: str) -> dict[str, Any]:
    policies = config["speech_policies"]
    roles = policies.get("roles", {})
    return roles.get(role, roles.get("viewer", {}))


def can_view_restricted(config: dict[str, Any], role: str) -> bool:
    policy = role_policy(config, role)
    return bool(policy.get("can_view_restricted_evidence"))


def restricted_categories(config: dict[str, Any]) -> set[str]:
    policies = config["speech_policies"]
    return {str(item) for item in policies.get("restricted_categories", [])}


def is_restricted_ref(ref: dict[str, Any], config: dict[str, Any]) -> bool:
    categories = restricted_categories(config)
    classification = str(ref.get("classification") or ref.get("sensitivity") or "").lower()
    category = str(ref.get("category") or ref.get("type") or "").lower()
    access = str(ref.get("access") or ref.get("access_level") or "").lower()
    return bool(
        ref.get("restricted")
        or ref.get("is_restricted")
        or classification in {"restricted", "confidential", "secret", "authority_only"}
        or access in {"restricted", "authority_only", "steward_only"}
        or category in categories
    )


def ref_identity(ref: dict[str, Any]) -> str:
    return str(ref.get("reference") or ref.get("id") or ref.get("uri") or ref.get("href") or "unreferenced")


def normalize_evidence_ref(ref: dict[str, Any], config: dict[str, Any], role: str) -> tuple[dict[str, Any] | None, bool]:
    restricted = is_restricted_ref(ref, config)
    allowed = can_view_restricted(config, role)
    if restricted and not allowed:
        visible = {
            "reference": ref_identity(ref),
            "type": ref.get("type") or ref.get("category") or "restricted_evidence",
            "source_layer": ref.get("source_layer") or "agents-layer",
            "restricted": True,
            "redacted": True,
            "redaction_reason": "role policy hides restricted evidence details",
        }
        if role_policy(config, role).get("hide_restricted_reference_ids", False):
            visible["reference"] = "restricted-ref-hidden"
        return visible, True

    visible = {
        "reference": ref_identity(ref),
        "type": ref.get("type") or ref.get("category") or "evidence",
        "source_layer": ref.get("source_layer") or "agents-layer",
        "classification": ref.get("classification") or ref.get("sensitivity") or "internal",
        "confidence": ref.get("confidence", "unknown"),
        "restricted": restricted,
    }
    text = ref.get("text") or ref.get("summary") or ref.get("excerpt")
    if text:
        visible["text"] = safe_text(text, 360)
    return visible, False


def refs_from_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for finding in findings:
        traceability = finding.get("traceability") if isinstance(finding.get("traceability"), dict) else {}
        for ref in as_list(finding.get("evidence_refs")) + as_list(traceability.get("evidence_refs")):
            if isinstance(ref, dict):
                refs.append(ref)
        for ref in as_list(finding.get("restricted_evidence_refs")):
            if isinstance(ref, dict):
                item = dict(ref)
                item["restricted"] = True
                refs.append(item)
    return refs


def filter_evidence_refs(raw_refs: list[dict[str, Any]], config: dict[str, Any], role: str) -> tuple[list[dict[str, Any]], int]:
    filtered: list[dict[str, Any]] = []
    hidden = 0
    seen: set[tuple[str, str]] = set()
    for ref in raw_refs:
        normalized, was_hidden = normalize_evidence_ref(ref, config, role)
        if normalized is None:
            continue
        key = (str(normalized.get("reference")), str(normalized.get("type")))
        if key in seen:
            continue
        seen.add(key)
        filtered.append(normalized)
        if was_hidden:
            hidden += 1
    return filtered, hidden


def finding_severity(finding: dict[str, Any]) -> str:
    value = str(finding.get("severity") or "medium").lower()
    return value if value in SEVERITY_RANK else "medium"


def aggregate_severity(findings: list[dict[str, Any]], assessment: dict[str, Any]) -> str:
    explicit = str(assessment.get("severity") or "").lower()
    if explicit in SEVERITY_RANK:
        return explicit
    if not findings:
        return "none"
    return max((finding_severity(item) for item in findings), key=lambda item: SEVERITY_RANK[item])


def assessment_status(findings: list[dict[str, Any]], assessment: dict[str, Any], severity: str) -> str:
    readiness = assessment.get("readiness") if isinstance(assessment.get("readiness"), dict) else {}
    explicit = str(assessment.get("assessment_status") or readiness.get("status") or "").strip()
    if explicit:
        return explicit
    if not findings:
        return "missing_context"
    return STATUS_BY_SEVERITY.get(severity, "review_required")


def confidence_value(assessment: dict[str, Any], evidence_count: int, hidden_count: int) -> float:
    explicit = assessment.get("confidence")
    if isinstance(explicit, (int, float)):
        return round(max(0.0, min(1.0, float(explicit))), 2)
    readiness = assessment.get("readiness") if isinstance(assessment.get("readiness"), dict) else {}
    score = readiness.get("score")
    if isinstance(score, (int, float)):
        return round(max(0.0, min(1.0, float(score) / 100.0)), 2)
    if evidence_count:
        return round(max(0.25, 0.72 - hidden_count * 0.04), 2)
    return 0.35


def missing_evidence_from(findings: list[dict[str, Any]], assessment: dict[str, Any]) -> list[str]:
    missing = set(str(item) for item in as_list(assessment.get("missing_evidence")) if str(item).strip())
    for finding in findings:
        for item in as_list(finding.get("missing_evidence")):
            if str(item).strip():
                missing.add(str(item))
    return sorted(missing)


def agent_versions_from(findings: list[dict[str, Any]], assessment: dict[str, Any], agent_ids: list[str]) -> dict[str, str]:
    versions: dict[str, str] = {}
    raw = assessment.get("agent_versions")
    if isinstance(raw, dict):
        versions.update({str(key): str(value) for key, value in raw.items()})
    for finding in findings:
        agent_id = str(finding.get("agent_id") or "").strip()
        traceability = finding.get("traceability") if isinstance(finding.get("traceability"), dict) else {}
        version = finding.get("agent_version") or traceability.get("agent_version")
        if agent_id and version:
            versions[agent_id] = str(version)
    for agent_id in agent_ids:
        versions.setdefault(agent_id, "unknown")
    return versions


def rule_traceability_from(findings: list[dict[str, Any]], assessment: dict[str, Any]) -> list[dict[str, Any]]:
    explicit = assessment.get("rule_traceability")
    if isinstance(explicit, list):
        return [item for item in explicit if isinstance(item, dict)]
    trace: list[dict[str, Any]] = []
    for finding in findings:
        finding_trace = finding.get("traceability") if isinstance(finding.get("traceability"), dict) else {}
        rule_id = finding.get("rule_id") or finding_trace.get("rule_id")
        rule_version = finding.get("rule_version") or finding_trace.get("rule_version")
        standard_refs = finding.get("standard_refs") or finding_trace.get("standard_refs") or finding.get("standards")
        assumptions = finding.get("assumptions") or finding_trace.get("assumptions")
        human_review_state = finding.get("human_review_state") or finding_trace.get("human_review_state")
        if not any([rule_id, rule_version, standard_refs, assumptions, human_review_state]):
            continue
        trace.append(
            {
                "agent_id": finding.get("agent_id") or finding_trace.get("agent_id") or "unknown-agent",
                "rule_id": rule_id or "unknown-rule",
                "rule_version": str(rule_version or "unknown"),
                "standard_refs": [str(item) for item in as_list(standard_refs) if str(item).strip()],
                "assumptions": [safe_text(item, 220) for item in as_list(assumptions) if str(item).strip()],
                "human_review_state": human_review_state or finding.get("status") or "review_required",
            }
        )
    return trace


def next_actions_from(findings: list[dict[str, Any]], missing: list[str], assessment: dict[str, Any]) -> list[str]:
    actions = [safe_text(item, 180) for item in as_list(assessment.get("next_actions")) if str(item).strip()]
    for finding in findings:
        action = finding.get("recommended_action") or finding.get("next_action")
        if action:
            actions.append(safe_text(action, 180))
    if missing:
        actions.append("Attach or validate missing evidence before product sign-off.")
    if not actions:
        actions.append("Route the advisory result to a human product or compliance reviewer.")
    result: list[str] = []
    seen: set[str] = set()
    for action in actions:
        if action and action not in seen:
            seen.add(action)
            result.append(action)
    return result[:6]


def display_summary_from(
    product_id: str,
    mode: str,
    status: str,
    severity: str,
    confidence: float,
    missing: list[str],
    hidden: int,
    findings: list[dict[str, Any]],
) -> str:
    parts = [
        f"Product {product_id} assessment mode {mode}: {status.replace('_', ' ')}.",
        f"Highest severity is {severity}; confidence is {int(confidence * 100)}%.",
    ]
    if findings:
        parts.append(f"{len(findings)} advisory finding(s) are available for review.")
    else:
        parts.append("No structured agent findings were supplied to the avatar layer.")
    if missing:
        parts.append("Missing evidence: " + ", ".join(missing[:5]) + ".")
    if hidden:
        parts.append(f"{hidden} restricted evidence reference(s) were redacted for this role.")
    parts.append("Advisory output only; human review and sign-off remain required.")
    return " ".join(parts)


def spoken_summary_from(display_summary: str, config: dict[str, Any], role: str) -> str:
    text = display_summary
    policy = role_policy(config, role)
    restricted_terms = [str(item) for item in config["speech_policies"].get("spoken_redaction_terms", [])]
    if not can_view_restricted(config, role) or policy.get("mute_restricted_detail_in_speech", True):
        for term in restricted_terms:
            if term:
                text = re.sub(re.escape(term), "restricted detail", text, flags=re.IGNORECASE)
    return safe_text(text, int(config["runtime"].get("speech", {}).get("max_spoken_chars", 520)))


def transcript_payload(spoken: str, display: str, body: dict[str, Any], product_id: str, mode: str, role: str) -> dict[str, Any]:
    session_id = str(body.get("session_id") or f"avatar-session-{uuid.uuid4().hex[:12]}")
    transcript_id = f"transcript-{uuid.uuid4().hex[:12]}"
    now = utc_now()
    return {
        "session_id": session_id,
        "transcript_id": transcript_id,
        "created_at": now,
        "language": str(body.get("language") or "en-US"),
        "product_id": product_id,
        "assessment_mode": mode,
        "viewer_role": role,
        "entries": [
            {
                "entry_id": f"entry-{uuid.uuid4().hex[:10]}",
                "speaker": "avatar",
                "kind": "spoken_summary",
                "text": spoken,
                "created_at": now,
            },
            {
                "entry_id": f"entry-{uuid.uuid4().hex[:10]}",
                "speaker": "avatar",
                "kind": "display_summary",
                "text": display,
                "created_at": now,
            },
        ],
    }


def avatar_assess(body: dict[str, Any], headers: Any | None = None) -> dict[str, Any]:
    config = config_payload()
    role = role_from_request(body, headers)
    assessment = get_assessment_payload(body)
    findings = [item for item in as_list(assessment.get("findings")) if isinstance(item, dict)]
    mode = assessment_mode(body, assessment, config)
    product_id = product_id_from(body, assessment)
    agent_ids = requested_agent_ids(body, assessment)

    raw_refs = [item for item in as_list(body.get("evidence_refs")) if isinstance(item, dict)]
    raw_refs += [item for item in as_list(assessment.get("evidence_refs")) if isinstance(item, dict)]
    raw_refs += refs_from_findings(findings)
    evidence_refs, hidden = filter_evidence_refs(raw_refs, config, role)

    severity = aggregate_severity(findings, assessment)
    status = assessment_status(findings, assessment, severity)
    missing = missing_evidence_from(findings, assessment)
    confidence = confidence_value(assessment, len(evidence_refs), hidden)
    product_context = product_context_from(body, product_id)
    human_review_required = True
    display = display_summary_from(product_id, mode, status, severity, confidence, missing, hidden, findings)
    spoken = spoken_summary_from(display, config, role)
    transcript = transcript_payload(spoken, display, body, product_id, mode, role)
    now = utc_now()
    audit_events = [
        {
            "event": "avatar_assessment_requested",
            "created_at": now,
            "product_id": product_id,
            "assessment_mode": mode,
            "viewer_role": role,
        },
        {
            "event": "spoken_summary_generated",
            "created_at": now,
            "product_id": product_id,
            "text_length": len(spoken),
            "restricted_refs_hidden": hidden,
        },
        {
            "event": "transcript_generated",
            "created_at": now,
            "product_id": product_id,
            "transcript_id": transcript["transcript_id"],
        },
    ]

    return {
        "schema_version": "0.1.0",
        "service": "avatar-layer",
        "created_at": now,
        "advisory_only": True,
        "product_id": product_id,
        "product_context": product_context,
        "assessment_mode": mode,
        "assessment_status": status,
        "severity": severity,
        "confidence": confidence,
        "spoken_summary": spoken,
        "display_summary": display,
        "evidence_refs": evidence_refs,
        "restricted_refs_hidden": hidden,
        "missing_evidence": missing,
        "human_review_required": human_review_required,
        "next_actions": next_actions_from(findings, missing, assessment),
        "agent_ids": agent_ids,
        "agent_versions": agent_versions_from(findings, assessment, agent_ids),
        "rule_traceability": rule_traceability_from(findings, assessment),
        "transcript": transcript,
        "audit_events": audit_events,
        "session": {
            "session_id": transcript["session_id"],
            "transcript_id": transcript["transcript_id"],
            "viewer_role": role,
            "speech_enabled": not bool(body.get("muted") or body.get("text_only")),
            "reduced_motion": bool(body.get("reduced_motion")),
            "text_only": bool(body.get("text_only")),
        },
        "source_contract": {
            "accepts_product_id": True,
            "accepts_agent_ids": True,
            "accepts_precomputed_assessment_payload": True,
            "mutates_product_layer": False,
            "mutates_agents_layer": False,
            "mutates_data_layer": False,
        },
    }


def client_config(config: dict[str, Any]) -> dict[str, Any]:
    runtime = config["runtime"]
    return {
        "service": runtime.get("service", {}),
        "integrations": runtime.get("integrations", {}),
        "speech": runtime.get("speech", {}),
        "avatar_profiles": config["avatar_profiles"],
        "assessment_modes": config["assessment_modes"],
        "policy": {
            "advisory_only": True,
            "human_review_required": True,
            "restricted_speech_guardrails": True,
        },
    }


class Handler(SimpleHTTPRequestHandler):
    server_version = "ThebenpaulAvatarLayer/0.1"

    def translate_path(self, path: str) -> str:
        parsed = urlparse(path)
        clean = parsed.path
        if clean in {"/", ""}:
            return str(STATIC_DIR / "index.html")
        resolved = (STATIC_DIR / clean.lstrip("/")).resolve()
        try:
            resolved.relative_to(STATIC_DIR.resolve())
        except ValueError:
            return str(STATIC_DIR / "index.html")
        return str(resolved)

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
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        config = config_payload()
        if path == "/health":
            return self.send_json({"status": "ok", "service": "avatar-layer", "time": utc_now()})
        if path in {"/api/config", "/config"}:
            return self.send_json(client_config(config))
        if path == "/api/profiles":
            return self.send_json(config["avatar_profiles"])
        if path == "/api/assessment-modes":
            return self.send_json(config["assessment_modes"])
        if path.startswith("/api/"):
            return self.send_json({"error": "not found", "path": path}, status=404)
        return super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path in {"/api/avatar/assess", "/api/assess"}:
            try:
                result = avatar_assess(self.read_json(), self.headers)
                append_audit_events(result.get("audit_events") or [])
                return self.send_json(result, status=201)
            except json.JSONDecodeError as exc:
                return self.send_json({"error": f"invalid JSON: {exc}"}, status=400)
        return self.send_json({"error": "not found", "path": path}, status=404)


def run(host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"avatar-layer listening on http://{host}:{port}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("avatar-layer shutdown requested", file=sys.stderr)
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Thebenpaul avatar-layer service")
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8095")))
    args = parser.parse_args()
    run(args.host, args.port)


if __name__ == "__main__":
    main()
