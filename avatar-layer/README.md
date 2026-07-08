# Thebenpaul Avatar Layer

Thin interaction layer for assessment playback in the Thebenpaul stack.

The avatar layer turns governed product-layer and agents-layer assessment payloads into display summaries, spoken summaries, transcript metadata, next actions, and role-filtered evidence references. It is advisory only and does not mutate product, agent, evidence, or certification records.

## Architecture

```text
product-layer Assess action
        |
        v
agents-layer advisory assessment
        |
        v
avatar-layer summary + transcript + speech policy
        |
        v
product-layer popup / browser Web Speech API
```

### Runtime Principles

- Dependency-free Python stdlib HTTP service.
- Static browser shell under `static/`.
- Browser Web Speech API for voice output when available.
- Text-only, mute, and reduced-motion states are supported.
- Evidence references are role-filtered before display or speech.
- Restricted evidence details are never spoken to viewer roles.

## Services

| Service | Port | Purpose |
|---------|------|---------|
| Avatar UI | 8095 | Static avatar assessment shell |
| Avatar API | 8095 | Config and assessment playback endpoints |

## Quick Start

### Local

```bash
cd /Users/Shared/code/paul/ihk-theben-challenge-2026/avatar-layer
python3 -B app/app.py --host 127.0.0.1 --port 8095
```

Open:

| Surface | URL |
|---------|-----|
| Avatar UI | http://127.0.0.1:8095/ |
| Health | http://127.0.0.1:8095/health |
| Client config | http://127.0.0.1:8095/api/config |
| Profiles | http://127.0.0.1:8095/api/profiles |
| Assessment modes | http://127.0.0.1:8095/api/assessment-modes |

### Docker

```bash
cd /Users/Shared/code/paul/ihk-theben-challenge-2026/avatar-layer
docker compose up -d --build
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service status and timestamp |
| GET | `/api/config` | Safe runtime config for the browser shell |
| GET | `/config` | Alias for `/api/config` |
| GET | `/api/profiles` | Avatar profile definitions |
| GET | `/api/assessment-modes` | Supported assessment modes |
| POST | `/api/avatar/assess` | Generate avatar playback contract |
| POST | `/api/assess` | Alias for `/api/avatar/assess` |

## Assessment Example

```bash
curl http://127.0.0.1:8095/api/avatar/assess \
  -H "Content-Type: application/json" \
  -H "X-Role: viewer" \
  -d '{
    "product_id": "THB-001",
    "agent_ids": ["expert-dpp-readiness"],
    "assessment_mode": "dpp",
    "assessment": {
      "readiness": {"status": "review_required", "score": 72},
      "findings": [
        {
          "agent_id": "expert-dpp-readiness",
          "severity": "medium",
          "status": "needs_review",
          "missing_evidence": ["environmental_declaration"],
          "recommended_action": "Add missing evidence before sign-off."
        }
      ]
    }
  }'
```

Response highlights:

- `spoken_summary`
- `display_summary`
- `assessment_status`
- `severity`
- `confidence`
- `evidence_refs`
- `restricted_refs_hidden`
- `missing_evidence`
- `human_review_required`
- `next_actions`
- `agent_versions`
- `transcript`
- `session`

## Configuration

Configuration lives under `config/`.

| File | Purpose |
|------|---------|
| `runtime.json` | Service name, integrations, speech, UI guardrails |
| `avatar_profiles.json` | Avatar persona/profile definitions |
| `speech_policies.json` | Role-based evidence and speech restrictions |
| `assessment_modes.json` | General, DPP, cybersecurity, and other playback modes |

Environment variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `HOST` | `127.0.0.1` locally, `0.0.0.0` in Docker | Bind host |
| `PORT` | `8095` | Service port |
| `THEBEN_AVATAR_ROLE_TOKEN` | empty locally / Compose default token | Optional role-token gate |
| `THEBEN_AVATAR_DEFAULT_ROLE` | `viewer` | Default viewer role |
| `THEBEN_AVATAR_TRUST_ROLE_HEADERS` | false | Trust `X-Role` without token |
| `THEBEN_AVATAR_TRUST_BODY_ROLE` | false | Trust request body role |
| `THEBEN_AVATAR_DATA_DIR` | `./data` | Audit event directory |

## Integration Boundaries

Reads from product-layer:

- Selected product ID and product context.
- Viewer role.
- Assessment mode.
- Precomputed agents-layer assessment payload.

Reads from agents-layer:

- Readiness status and score.
- Findings, severities, missing evidence, and next actions.
- Rule and agent traceability.
- Evidence references.

Writes:

- Avatar playback JSON response.
- Local audit event lines in `data/avatar_audit.jsonl` when called through the API.

Does not write:

- Product master data.
- DPP records.
- Agent findings.
- Raw evidence.
- Certification state.

## Browser Behavior

- Uses the Web Speech API when supported by the browser.
- Keeps text output available when speech is unsupported or disabled.
- Applies speech policies before producing spoken text.
- Keeps restricted evidence details out of viewer speech.

## Validation

Run unit tests:

```bash
cd /Users/Shared/code/paul/ihk-theben-challenge-2026/avatar-layer
python3 -B -m unittest discover -s tests -v
```

Python syntax check:

```bash
cd /Users/Shared/code/paul/ihk-theben-challenge-2026/avatar-layer
python3 -B -m py_compile app/app.py
```

## Data Files

| Path | Purpose |
|------|---------|
| `static/index.html` | Browser shell |
| `static/app.js` | Assessment playback client |
| `static/styles.css` | Avatar-layer styling |
| `config/` | Runtime, speech, profile, and mode configuration |
| `data/avatar_audit.jsonl` | Local audit event log |
| `tests/` | Contract and policy tests |

## Operations

Restart after config or code changes:

```bash
docker compose up -d --build
```

Inspect logs:

```bash
docker compose logs -f avatar-layer
```
