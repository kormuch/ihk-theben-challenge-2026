# Thebenpaul Agents Layer

Lean implementation for the `compliance-agents-layer` and `expert-agents-layer` described in `Thebenpaul/goal_expert-agent.md`.

The first wave is intentionally lightweight:

- One stdlib Python REST service.
- File-based configuration under `config/`.
- Deterministic advisory checks.
- JSON outputs with traceability.
- Docker Compose runtime.
- LAN Ollama configuration as an advisory provider setting.
- No product master data ownership.
- No raw evidence ownership.
- No formal certification or engineering sign-off.

## Run

```bash
python3 -m app.app --host 127.0.0.1 --port 8090
```

Open:

- Dashboard: <http://127.0.0.1:8090/>
- Health: <http://127.0.0.1:8090/health>
- Agents: <http://127.0.0.1:8090/api/agents>
- Standards validity: <http://127.0.0.1:8090/api/standards-validity>

## Docker

```bash
docker compose up --build
```

## Validate

```bash
scripts/validate.sh
```

Docker test profile:

```bash
docker compose --profile test run --rm test
```

## Assessment Example

```bash
curl -H 'X-Role: reviewer' -H 'Content-Type: application/json' \
  -d '{
    "target_market": "EU",
    "date_placing_on_market": "2026-07-06",
    "product": {
      "id": "THB-DEMO-001",
      "family": "KNX Actuator",
      "lifecycle_state": "draft",
      "attributes": {
        "gtin": "04003468000001",
        "batch_lot_number": "LOT-001",
        "serial_number": "SN-001",
        "nominal_voltage": "230V",
        "recyclable_share_pct": 82,
        "co2_kg": 1.4
      },
      "metadata": {
        "owner": "Product Data Domain",
        "domain": "product",
        "source_system": "product-layer",
        "lineage": "data-layer -> product-layer",
        "classification": "internal",
        "certification_status": "draft"
      }
    },
    "evidence": [
      {"type": "product_master_record", "reference": "product-layer/THB-DEMO-001", "confidence": "verified"},
      {"type": "lineage_record", "reference": "lineage/THB-DEMO-001", "confidence": "high"}
    ]
  }' \
  http://127.0.0.1:8090/api/assessments
```

## Config

Minimum goal configuration is present:

- `config/ai_agents.md`
- `config/standards_validity.md`
- `config/compliance_sustainability_skill.md`
- `config/compliance_emc_skill.md`
- `config/compliance_cybersecurity_skill.md`
- `config/compliance_wireless_skill.md`
- `config/compliance_privacy_skill.md`
- `config/expert_dpp_readiness.md`
- `config/expert_sustainability.md`
- `config/expert_emc_design.md`
- `config/expert_cybersecurity_quality.md`
- `config/expert_governance.md`
- `config/expert_cad_mechanical.md`
- `config/expert_pricing_sales_market.md`
- `config/expert_aftermarket_service.md`
- `config/rule_catalog.json`
- `config/evidence_model.json`
- `config/access_control.json`
- `config/runtime.json`

## Integration Boundaries

Reads from product-layer:

- Product master records.
- Product family and lifecycle state.
- DPP records.
- Product identity and Data Matrix fields.
- Validation results, sync state, and lineage.

Reads from data-layer:

- Extracted evidence.
- Source document references.
- Test reports, certificates, declarations, SBOMs, and standards documents.
- Lineage and extraction metadata.

Writes:

- Advisory findings.
- Gap summaries.
- Missing evidence flags.
- Readiness status.
- Review recommendations.
- Mempalace-ready summaries.

The service does not mutate product master data, DPP records, raw evidence, or formal certification state.

