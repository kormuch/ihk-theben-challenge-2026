# Thebenpaul Agents Layer

Lightweight advisory runtime for the `compliance-agents-layer` and `expert-agents-layer`.

The agents layer evaluates governed product-layer records and data-layer evidence references against configurable rules. It returns advisory findings, missing evidence, readiness status, and traceability. It does not own product master data, raw evidence, DPP records, or formal certification decisions.

## Architecture

```text
product-layer selected product
        |
        v
agents-layer assessment runtime
        |
        +-- config/rule_catalog.json
        +-- config/evidence_model.json
        +-- config/*_skill.md
        +-- config/standards_validity.md
        |
        v
advisory findings + readiness + traceability
        |
        v
product-layer UI / avatar-layer playback / Mempalace documentation
```

### Runtime Principles

- Dependency-light Python stdlib HTTP service.
- Configuration-as-code under `config/`.
- Deterministic checks for the first implementation wave.
- Advisory output only; human review and sign-off remain mandatory.
- Product-layer and data-layer stay authoritative for product and evidence data.
- LAN Ollama settings are present for advisory assistance, but the current rule runtime does not require an LLM.

## Services

| Service | Port | Purpose |
|---------|------|---------|
| Agents dashboard | 8090 | Human-readable service overview |
| Agents API | 8090 | Agent catalog, standards validity, assessments |
| Test profile | n/a | Containerized validation via Docker Compose |

## Quick Start

### Local

```bash
cd /Users/Shared/code/paul/ihk-theben-challenge-2026/agents-layer
python3 -B -m app.app --host 127.0.0.1 --port 8090
```

Open:

| Surface | URL |
|---------|-----|
| Dashboard | http://127.0.0.1:8090/ |
| Health | http://127.0.0.1:8090/health |
| Agents catalog | http://127.0.0.1:8090/api/agents |
| Standards validity | http://127.0.0.1:8090/api/standards-validity |
| Open items | http://127.0.0.1:8090/api/open-items |

### Docker

```bash
cd /Users/Shared/code/paul/ihk-theben-challenge-2026/agents-layer
docker compose up -d --build
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service status and timestamp |
| GET | `/api/agents` | Compliance and expert agent catalog |
| GET | `/api/compliance-agents` | Compliance agents only |
| GET | `/api/expert-agents` | Expert agents only |
| GET | `/api/standards-validity` | Machine-readable standards validity table |
| GET | `/api/integrations` | Runtime integration contract |
| GET | `/api/open-items` | Known open validation or configuration items |
| POST | `/api/assessments` | Run advisory assessment |

## Assessment Example

Reviewer/admin calls need a trusted role token unless role-header trust is explicitly enabled.

```bash
curl http://127.0.0.1:8090/api/assessments \
  -H "Content-Type: application/json" \
  -H "X-Role: reviewer" \
  -H "X-Role-Token: ${THEBEN_AGENTS_LAYER_ROLE_TOKEN:-local-dev-agents-token}" \
  -d '{
    "target_market": "EU",
    "date_placing_on_market": "2026-07-06",
    "agent_ids": ["expert-dpp-readiness"],
    "product": {
      "id": "THB-DEMO-001",
      "family": "KNX Actuator",
      "lifecycle_state": "draft",
      "attributes": {
        "gtin": "04003468000001",
        "batch_lot_number": "LOT-001",
        "serial_number": "SN-001",
        "nominal_voltage": "230V"
      },
      "metadata": {
        "owner": "Product Data Domain",
        "domain": "product",
        "source_system": "product-layer",
        "lineage": "data-layer -> product-layer",
        "classification": "internal"
      }
    },
    "evidence": [
      {"type": "product_master_record", "reference": "product-layer/THB-DEMO-001", "confidence": "verified"},
      {"type": "lineage_record", "reference": "lineage/THB-DEMO-001", "confidence": "high"}
    ]
  }'
```

## Configuration

The service reads editable configuration from `config/`.

| File | Purpose |
|------|---------|
| `runtime.json` | Service settings, integration URLs, enabled agents |
| `rule_catalog.json` | Compliance/expert agents and rule definitions |
| `evidence_model.json` | Evidence types and expected source contracts |
| `access_control.json` | Roles, permissions, and runtime access rules |
| `standards_validity.md` | Standards validity table used by the API |
| `ai_agents.md` | Agent portfolio description |
| `compliance_*_skill.md` | Compliance agent skill prompts |
| `expert_*.md` | Expert agent skill prompts |

Default integration URLs:

| Layer | URL | Role |
|-------|-----|------|
| Product layer | `http://host.docker.internal:8080` | Product, DPP, validation and lineage context |
| Data layer | `http://host.docker.internal:8000` | Evidence references and exported product records |
| Ollama LAN | `http://192.168.178.60:11434` | Optional advisory assistance provider |

## Integration Boundaries

Reads from product-layer:

- Product master records.
- Product family and lifecycle state.
- DPP records and identity fields.
- Validation results, sync state, and lineage.

Reads from data-layer:

- Extracted evidence references.
- Source document references.
- Test reports, certificates, declarations, SBOMs, and standards documents.
- Lineage and extraction metadata.

Writes:

- Advisory findings.
- Gap summaries.
- Missing evidence flags.
- Readiness status.
- Review recommendations.
- Mempalace-ready documentation summaries.

Does not write:

- Product master records.
- Raw evidence.
- DPP records.
- Formal certification or engineering sign-off state.

## Validation

Local validation:

```bash
cd /Users/Shared/code/paul/ihk-theben-challenge-2026/agents-layer
scripts/validate.sh
```

Docker validation:

```bash
cd /Users/Shared/code/paul/ihk-theben-challenge-2026/agents-layer
docker compose --profile test run --rm test
```

Python unit tests:

```bash
cd /Users/Shared/code/paul/ihk-theben-challenge-2026/agents-layer
python3 -B -m unittest discover -s tests -v
```

## Data Files

| Path | Purpose |
|------|---------|
| `data/assessments.json` | Last advisory assessment outputs, capped by the service |
| `config/` | Versioned agent, rules, evidence, role, and integration definitions |
| `tests/` | Contract and rule-behavior tests |

## Operations

Restart after config or code changes:

```bash
docker compose up -d --build
```

Inspect logs:

```bash
docker compose logs -f agents-layer
```
