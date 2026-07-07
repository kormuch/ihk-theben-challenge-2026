# Thebenpaul Product Layer

The product layer is the domain-owned product data module inside the Thebenpaul lakehouse architecture. It exposes curated, governed, documented, and quality-tested product information through a local Web UI, REST APIs, OpenAPI docs, Digital Product Passport views, exports, and integration contracts.

The implementation is intentionally lean: a Python stdlib service, static UI, JSON adapter store for the MVP, Docker Compose runtime, and config-as-code for metadata, access control, quality, DPP, AI colleague, agents-layer, and avatar-layer integration.

## Purpose

The product layer demonstrates how one business domain can own a curated data product while central IT keeps platform standards, security, catalog, lineage, observability, and tooling consistent.

It supports:

- Product overview, search, filtering, and attribute editing.
- Data Matrix identity fields: GTIN, batch/lot, and serial number.
- Digital Product Passport API and public HTML preview.
- Data-layer synchronization and flow debugging.
- Agent assessments for DPP, cybersecurity, compliance, and governance review.
- Avatar-layer presentation for spoken or popup assessment summaries.
- Governance, metadata, quality, lineage, and access policy transparency.
- REST, OpenAPI, CSV, printable HTML, SVG, DPP, and controlled export surfaces.

## Architecture Alignment

The Thebenpaul target architecture is a central lakehouse platform with separate domain modules inside it.

For product-layer this means:

- Central IT owns platform security, catalog, lineage, observability, shared standards, backup, monitoring, patching, and platform tooling.
- The product domain owns business meaning, transformations, data product definitions, quality rules, and curated dataset certification.
- Product-layer consumes standardized or curated product data from the data-layer and exposes stable business-facing consumption interfaces.
- The solution stays open source first, Docker-first, generic, informative, interactive, and suitable for a company-managed VM.

Design principles:

- **Abstraktion**: product-layer contracts stay stable even when physical storage changes.
- **Generisch**: multiple product families, source systems, and consumers can use the same patterns.
- **Informativ**: metadata, lineage, ownership, certification, quality, and access rules are visible.
- **Interaktiv**: users can explore, edit, validate, preview, assess, sync, and debug product data.

## Lakehouse Position

Target flow:

```text
source systems
  -> data-layer raw ingestion
  -> data-layer standardized model
  -> Apache Iceberg standardized tables
  -> Apache Iceberg curated product data product
  -> product-layer REST, UI, DPP, exports, agents, avatar
```

Current executable MVP flow:

```text
data-layer export or local import
  -> product-layer JSON adapter
  -> product-layer validation, governance metadata, and DPP projection
  -> REST API, Web UI, exports, agents-layer assessment, avatar-layer presentation
```

The JSON store is an adapter boundary for local execution. The intended target remains Apache Iceberg as the lakehouse table format, with governed SQL views or APIs exposed through the platform.

## Data Product

A data product is a domain-owned, documented, versioned, and quality-tested asset.

Initial product data product:

```text
Name: product-master-dpp
Domain: product
Owner: Product Data Domain
Steward: product-data-steward@thebenpaul.local
Target table: curated_product.product_master_dpp
Target table format: Apache Iceberg
Contract version: 0.1.0
```

Every exposed curated dataset should have:

- Owner, domain, source, lineage, refresh frequency, SLA, classification, and certification status.
- Versioned contract and lifecycle state.
- Quality checks and test evidence.
- Approved consumption channels.
- Clear deprecation and incident handling rules.

## Repository Structure

```text
product-layer/
  app/
    app.py                         Product-layer API, UI, sync, DPP, validation, proxy logic
  config/
    access_control.json            RBAC, ABAC, row-level security, masking, layer access
    ai_integration.json            AI colleague registry, default Ollama LAN provider
    dpp_schema.json                Digital Product Passport schema and access model
    metadata_schema.json           Data product metadata and identity contract
    quality_rules.json             Product quality rules and identity requirements
    runtime.json                   Service, data-layer, agents-layer, avatar-layer, Ollama defaults
  data/
    products.json                  Local MVP adapter store, generated or synchronized
  docs/
    architecture.md                Product-layer architecture notes
  scripts/
    debug-data-flow.sh             Data-layer to product-layer flow debugger
    validate.sh                    Standard validation entrypoint
  static/
    index.html                     Web UI shell
    app.js                         UI behavior
    styles.css                     UI styles
  tests/
    test_app.py                    Unit and HTTP validation tests
  docker-compose.yml               Product-layer and Ollama runtime
  Dockerfile                       Product-layer container
  README.md                        Canonical product-layer documentation
```

## Run Locally

```bash
python3 -m app.app --host 127.0.0.1 --port 8080
```

Open:

- Web UI: <http://127.0.0.1:8080/>
- API docs: <http://127.0.0.1:8080/docs>
- OpenAPI JSON: <http://127.0.0.1:8080/api/openapi.json>

The first run creates `data/products.json` with generated product records.

Use another port when `8080` is already occupied:

```bash
python3 -m app.app --host 127.0.0.1 --port 8120
```

## Run With Docker Compose

```bash
docker compose up --build
```

This starts:

- `product-layer` on `0.0.0.0:${PRODUCT_LAYER_PORT:-8080}`.

It does not start a local Ollama service by default. Product-layer uses the configured LAN Ollama endpoint at `http://192.168.178.60:11434` so it does not compete with data-layer on host port `11434`.

Use a different product-layer port:

```bash
PRODUCT_LAYER_PORT=8120 docker compose up --build
```

If you intentionally need an isolated product-layer Ollama container, start the opt-in profile. It publishes to host port `11435` by default to avoid shadowing the LAN Ollama service on `11434`:

```bash
docker compose --profile local-ollama up -d ollama
docker compose --profile local-ollama exec ollama ollama pull gpt-oss:20b
```

## AI Colleagues

AI colleague configuration lives in:

```text
config/ai_integration.json
```

Default provider:

```text
Provider: ollama_lan
Base URL: http://192.168.178.60:11434
Model: gpt-oss:20b
Network scope: LAN
```

Alternative local provider:

```text
Provider: ollama_localhost
Base URL: http://localhost:11434
Model: gpt-oss:20b
Network scope: localhost
```

Smoke-test the LAN provider:

```bash
curl http://192.168.178.60:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss:20b","prompt":"Elaborate weather gradient for Stuttgart the next days.","stream":false}'
```

Smoke-test the local provider:

```bash
curl http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss:20b","prompt":"Elaborate weather gradient for Stuttgart the next days.","stream":false}'
```

Governance rules:

- AI outputs are suggestions only.
- Human review is required before product data, metadata, DPP, certification, or quality state changes.
- Do not send personal, confidential, financial, customer, or protected telemetry data to an AI colleague unless the provider is approved for that classification.
- Central IT owns AI provider approval, network policy, logging policy, and model access policy.

## Governance and Access Control

Product-layer demonstrates governance controls locally through `config/access_control.json`.

Supported control types:

- RBAC for role-based permissions.
- ABAC placeholders for role, purpose, region, and classification.
- Row-level security for regional product visibility.
- Column masking for confidential attributes.
- Layer-based access rules for raw, standardized, curated, and consumption layers.

Demo roles:

```text
viewer   -> read governed product data in the user's region
editor   -> read, import, and update product attributes
steward  -> cross-region domain steward with unmasked commercial attributes
admin    -> central IT/platform administrator for MVP operations
```

Trusted role headers are ignored by default. For local privileged testing, configure `THEBEN_ROLE_TOKEN` or `THEBEN_TRUST_ROLE_HEADERS=true` and use token-gated trusted role headers:

```bash
curl -H "X-Role: ${THEBEN_TRUSTED_ROLE}" \
  -H "X-Role-Token: ${THEBEN_ROLE_TOKEN}" \
  http://127.0.0.1:8080/api/data-product
```

Production target:

- Replace token-gated local role headers with SSO/IAM claims.
- Enforce policies in platform security, governed SQL views, and APIs.
- Audit read, write, import, sync, export, agent, avatar, and DPP access.
- Keep direct raw access limited to approved engineering, audit, and diagnostic use cases.

## Metadata and Quality

Mandatory metadata is defined in:

```text
config/metadata_schema.json
```

Quality rules are defined in:

```text
config/quality_rules.json
```

Validation checks include:

- Required metadata completeness.
- Required generic product attributes.
- Product-family-specific attributes.
- Numeric range checks.
- Certification policy checks.
- GTIN, batch/lot, and serial number identity fields.
- DPP identity payload readiness.

Quality policy:

- Certified datasets require no error-level quality issues.
- Warning-level issues require review.
- Schema and contract changes should be versioned.
- Deprecation needs a published timeline, migration path, and consumer notification.
- Incidents should include owner, severity, root cause, corrective action, and verification.

## Product Identity and Data Matrix

Product-layer tracks the identifiers needed for a GS1 DataMatrix-style payload:

- `attributes.gtin`: Global Trade Item Number for the trade item. Identical trade items from the same source use the same GTIN.
- `attributes.batch_lot_number`: production batch or lot for products sharing the same GTIN.
- `attributes.serial_number`: unique product instance identifier. GTIN plus serial number is globally unique.

The DPP/passport API derives:

```text
(01){gtin_14}(10){batch_lot_number}(21){serial_number}
```

## Digital Product Passport

DPP configuration lives in:

```text
config/dpp_schema.json
```

The DPP module supports public, B2B, and authority-oriented access levels, model/batch/item granularity, public DPP URL generation, product identity, origin, materials, repairability, end-of-life, environmental performance, compliance documentation, service lifecycle data, and authority-only compliance data.

Endpoints:

```text
GET /dpp/{product-id}
GET /api/dpp/{product-id}?view=consumer|b2b|authority
GET /api/dpp/{product-id}/versions
GET /api/dpp/{product-id}/audit
GET /api/dpp/scan?code={public-url-or-structured-id}
```

Public DPP URLs are generated from `THEBEN_PUBLIC_BASE_URL` when set, otherwise from `config/runtime.json` `service.public_base_url`. Keep this value stable and HTTPS-ready because Data Matrix payloads may be printed on products and must not drift by caller host.

## Agents and Avatar

Product-layer can call the agents-layer for advisory assessments and the avatar-layer for popup/spoken presentation.

Runtime defaults live in `config/runtime.json`:

```text
agents-layer: http://host.docker.internal:8090
avatar-layer: http://host.docker.internal:8095
```

The UI exposes agent assessment actions below validation. The selected product is sent as the assessment basis, so DPP, cybersecurity, compliance, and portfolio assessments can differ by product context and missing evidence.

Important rules:

- Agent output is advisory only.
- Avatar output is presentation only.
- Product master, DPP records, evidence, and certification state remain human-reviewed domain assets.
- Product-layer proxies service role headers with token-gated runtime configuration.

Representative calls:

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"product_id":"luxa-200-360","agent_ids":["expert-dpp-readiness"]}' \
  http://127.0.0.1:8080/api/agents-layer/assessments

curl -X POST -H "Content-Type: application/json" \
  -d '{"product_id":"luxa-200-360","assessment_mode":"portfolio","assessment":{"readiness":{"status":"blocked"},"findings":[]}}' \
  http://127.0.0.1:8080/api/avatar-layer/assessments
```

## Data-Layer Integration

The current executable bridge uses the data-layer export endpoint:

```text
/api/v1/export/products.json
```

Local host example:

```bash
THEBEN_DATA_LAYER_SYNC_ENABLED=true \
THEBEN_DATA_LAYER_EXPORT_URL=http://127.0.0.1:8000/api/v1/export/products.json \
python3 -m app.app --host 127.0.0.1 --port 8080
```

Docker Desktop for Mac/Windows default:

```text
http://host.docker.internal:8000/api/v1/export/products.json
```

Trigger sync:

```bash
curl -X POST \
  -H "X-Role: ${THEBEN_TRUSTED_ROLE}" \
  -H "X-Role-Token: ${THEBEN_ROLE_TOKEN}" \
  http://127.0.0.1:8080/api/sync/data-layer
```

Data-layer confirmation/export writes product-layer-shaped payloads to `product-layer/data/products.json` when `PRODUCT_LAYER_DATA_DIR` is mounted. Product-layer also exposes explicit pull sync at `/api/sync/data-layer`.

The product-layer store auto-reloads the shared JSON file on reads by default:

```bash
THEBEN_STORE_AUTO_RELOAD=true
```

Debug the bridge:

```bash
./scripts/debug-data-flow.sh
```

Debug and trigger sync:

```bash
./scripts/debug-data-flow.sh --sync
```

Override endpoints:

```bash
DATA_EXPORT_URL=http://127.0.0.1:8000/api/v1/export/products.json \
PRODUCT_URL=http://127.0.0.1:8080 \
./scripts/debug-data-flow.sh --sync
```

The sync records upstream schema version, export timestamp, domain module, lakehouse layer, and import errors in `sync_state`. Fetching includes retry with exponential backoff for transient network errors and HTTP 5xx responses. Client errors fail immediately.

## API Examples

```bash
curl http://127.0.0.1:8080/api/products?search=knx
curl http://127.0.0.1:8080/api/summary
curl http://127.0.0.1:8080/api/catalog/data-products
curl http://127.0.0.1:8080/api/data-product
curl http://127.0.0.1:8080/api/lineage
curl http://127.0.0.1:8080/api/access-policy
curl http://127.0.0.1:8080/api/integrations/data-layer
```

Create a product:

```bash
curl -H "X-Role: ${THEBEN_TRUSTED_ROLE}" \
  -H "X-Role-Token: ${THEBEN_ROLE_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"sku":"THB-DEMO-1","name":"Demo","family":"Time Switch","attributes":{"gtin":"04003468999999","batch_lot_number":"LOT-2026-001","serial_number":"SN-0000000001","nominal_voltage":"230V","ip_rating":"IP20","co2_kg":1.2,"recyclable_share_pct":82}}' \
  http://127.0.0.1:8080/api/products
```

Read DPP views:

```bash
curl http://127.0.0.1:8080/api/dpp/thb-tim-0001?view=consumer
curl -H "X-Role: ${THEBEN_TRUSTED_ROLE}" -H "X-Role-Token: ${THEBEN_ROLE_TOKEN}" http://127.0.0.1:8080/api/dpp/thb-tim-0001?view=authority
curl http://127.0.0.1:8080/dpp/thb-tim-0001
```

## Governance Endpoints

- `/api/catalog/data-products`: domain-owned data product definition, mandatory metadata, target Iceberg table, and approved interfaces.
- `/api/data-product`: access-aware data product surface with sync state, interfaces, mandatory metadata, and caller permissions.
- `/api/lineage`: raw -> standardized -> curated -> consumption lakehouse path with layer ownership and access rules.
- `/api/access-policy`: RBAC, ABAC attributes, row-level security, masking, layer access, and caller-effective permissions.
- `/api/integrations/data-layer`: active data-layer export contract and sync settings.
- `/api/sync/data-layer`: GET sync configuration/state or POST a data-layer import refresh.

## Tests

Use the project validation runner so local, Docker, and CI checks stay aligned:

```bash
scripts/validate.sh all
```

Modes:

```text
scripts/validate.sh unit    sandbox-friendly unit/parser/model checks
scripts/validate.sh live    HTTP tests against TEST_BASE_URL
scripts/validate.sh docker  Docker host-to-container and Compose test profile
scripts/validate.sh all     unit, then docker
```

Raw local unit command:

```bash
python3 -B -m unittest discover -s tests -v
```

Raw live endpoint command:

```bash
python3 -m app.app --host 127.0.0.1 --port 8120
TEST_BASE_URL=http://127.0.0.1:8120 python3 -B -m unittest discover -s tests -v
```

Raw Docker/CI command:

```bash
docker compose --profile test run --rm test
```

Use `PRODUCT_LAYER_PORT=8120` if the host already has something on `8080`.

Testing standard:

- Prefer `scripts/validate.sh all` before release notes or Mempalace loop documentation.
- Use `TEST_BASE_URL` for portable HTTP tests.
- Use Docker service names in containerized test profiles.
- Make Docker socket and context errors explicit instead of silently skipping container validation.

## Consumption Channels

Approved product-layer consumption channels:

- Web UI for interactive product exploration.
- REST APIs for operational apps and integrations.
- OpenAPI JSON for generated clients and documentation.
- BI and analytics consumers through future governed views or semantic models.
- DPP HTML pages for public label scans.
- Controlled exports such as CSV, printable HTML, PDF-ready pages, and images where supported.
- Controlled external sharing only through approved interfaces.

Direct access to raw data should remain limited to approved engineering, audit, or diagnostic use cases.

## Lifecycle and Change Management

Data product lifecycle states:

```text
draft -> certified -> deprecated -> retired
```

Required practices:

- Test every schema, transformation, sync contract, and quality-rule change.
- Version data product contracts and interface changes.
- Track release notes in GitHub.
- Track important architecture decisions, learnings, incidents, and release notes in Mempalace.
- Publish deprecation timelines and migration paths.
- Notify consumers before breaking changes.
- Keep configuration, metadata rules, quality checks, and deployment definitions as code.

## Implementation Waves

Wave 1 foundation:

- Lakehouse foundation.
- Governance model.
- Metadata standards.
- Access controls.
- Core ingestion and sync patterns.
- Product-layer local MVP.

Wave 2 product value:

- Product-master-DPP data product.
- Product overview.
- Attribute editor.
- Data Matrix identity.
- DPP preview.
- Product quality checks.
- Data-layer bridge.

Wave 3 connected and energy use cases:

- Connected-device, IoT, building automation, and energy attributes.
- Telemetry integration patterns.
- Additional product lifecycle and service data.

Wave 4 enterprise expansion:

- Manufacturing, finance, advanced analytics, operational APIs, controlled external sharing, production catalog, lineage, monitoring, and audit.

## Production Readiness Checklist

Before production use, resolve or confirm:

- SSO/IAM integration replaces token-gated trusted role headers.
- TLS reverse proxy is configured.
- Firewall rules are reviewed for product-layer, agents-layer, avatar-layer, and Ollama ports.
- Persistent volumes have backup and restore procedures.
- GitHub CI runs unit, live, Docker, and contract tests.
- OpenMetadata publication is planned or implemented.
- Apache Iceberg target table and Trino access path are defined.
- Data-layer export contract is versioned.
- Access policies are enforced centrally and at consumption interfaces.
- Audit logging covers reads, writes, imports, syncs, exports, agent calls, avatar calls, and DPP access.
- Mempalace documentation loops are used for decisions, learnings, incidents, and release notes.
- Central IT approves security, backup, monitoring, patching, and production readiness.

## Key Config Files

| File | Purpose |
| --- | --- |
| `config/metadata_schema.json` | Data product definition, mandatory metadata, lineage, identity, lifecycle |
| `config/quality_rules.json` | Required attributes, Data Matrix identity policy, numeric ranges, certification policy |
| `config/access_control.json` | RBAC, ABAC, row-level security, masking, layer access |
| `config/dpp_schema.json` | DPP tiers, granularity, access levels, data carrier rules |
| `config/runtime.json` | Service defaults, public base URL, data-layer, agents-layer, avatar-layer, sync config, Ollama defaults |
| `config/ai_integration.json` | AI colleague provider registry and governance policy |

## Success Criteria

The product layer is successful when it:

- Provides a useful local product data experience.
- Shows how a curated product data product works in the lakehouse architecture.
- Keeps ownership, metadata, lineage, access, quality, and certification visible.
- Supports both human UI workflows and API consumers.
- Demonstrates DPP and Data Matrix readiness.
- Integrates cleanly with the data-layer without coupling to raw ingestion internals.
- Integrates advisory agents and avatar presentation without mutating governed product data.
- Runs reproducibly with Docker Compose.
- Can be validated locally, in Docker, and in CI with the same test strategy.
- Can evolve from JSON adapter to Apache Iceberg-backed curated data product without breaking the business-facing product-layer contract.
