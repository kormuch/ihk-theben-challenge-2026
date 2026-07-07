# Thebenpaul Product Layer

Draft README proposal for enriching the product-layer documentation with the initial architecture goal from `Thebenpaul/goal.md`.

This file is a proposal. The current `README.md` is unchanged.

## 1. Purpose

The product layer is the domain-owned product data module inside the Thebenpaul lakehouse architecture.

Its job is to expose curated, governed, documented, and quality-tested product information through practical business interfaces:

- Product overview and search.
- Product attribute editing.
- Data Matrix identity fields.
- Digital Product Passport preview.
- REST APIs and OpenAPI documentation.
- Export and sharing interfaces.
- Data-layer synchronization.
- Governance, metadata, quality, and access policy transparency.

The product layer demonstrates how one business domain can own its curated data product while central IT keeps platform standards, security, catalog, lineage, observability, and tooling consistent.

## 2. Architecture Goal Alignment

The architecture target is a central lakehouse platform with separate domain modules inside it.

For the product layer, this means:

- The central platform owns raw ingestion, storage, platform security, catalog, lineage, observability, and shared standards.
- The product domain owns product business meaning, transformations, data product definitions, quality rules, and certification of curated datasets.
- The product layer consumes standardized or curated product data from the data-layer and exposes stable consumption interfaces.
- The solution stays open source first, Docker-first, generic, informative, interactive, and suitable for a company-managed VM.

Design principles:

- **Abstraktion**: keep product-layer interfaces stable even when the physical storage changes.
- **Generisch**: support multiple product families, source systems, and downstream consumers.
- **Informativ**: make metadata, quality, lineage, ownership, certification, and access rules visible.
- **Interaktiv**: support UI exploration, edits, validation, DPP preview, sync, and debugging workflows.

## 3. Lakehouse Position

Target lakehouse flow:

```text
source systems
  -> data-layer raw ingestion
  -> data-layer standardized model
  -> Apache Iceberg standardized tables
  -> Apache Iceberg curated product data product
  -> product-layer REST, UI, exports, DPP, APIs
```

Current executable MVP flow:

```text
mock/import/data-layer export
  -> product-layer JSON adapter
  -> product-layer validation and governance metadata
  -> REST API, Web UI, DPP, export
```

The JSON store is an adapter boundary for local execution. The intended target is Apache Iceberg as the lakehouse table format, with governed views or APIs exposed by the platform, for example through Trino.

## 4. Data Product Definition

The initial product data product is:

```text
Name: product-master-dpp
Domain: product
Owner: Product Data Domain
Steward: product-data-steward@thebenpaul.local
Target table: curated_product.product_master_dpp
Target table format: Apache Iceberg
Contract version: 0.1.0
```

A data product is a domain-owned, documented, versioned, and quality-tested asset.

For this product layer, that means every exposed curated dataset should have:

- Owner.
- Domain.
- Source system or source feed.
- Lineage.
- Refresh frequency.
- SLA.
- Classification.
- Certification status.
- Versioned contract.
- Quality checks.
- Approved consumption channels.
- Clear lifecycle status.

## 5. Responsibilities

Central IT or data platform owns:

- Platform architecture and operations.
- Platform security.
- Catalog and metadata standards.
- Lineage.
- Observability.
- Shared tooling and engineering standards.
- Cross-domain integration standards.
- Backup, monitoring, patching, and production readiness.

Product domain owns:

- Product data product definition.
- Business meaning and semantic rules.
- Product-specific transformations.
- Quality rules.
- Product attribute certification.
- Curated dataset certification.
- Prioritization of product analytics and DPP use cases.

## 6. Current Feature Scope

The current product layer provides:

- Python stdlib REST service.
- Static Web UI.
- OpenAPI JSON.
- Swagger-style docs endpoint.
- Product list, search, and filters.
- Product upload/import flow.
- Attribute editor.
- Validation and quality status.
- Data product catalog endpoint.
- Lineage endpoint.
- Access policy endpoint.
- Data-layer integration status and sync endpoint.
- Digital Product Passport API and HTML preview.
- GS1 DataMatrix identity payload derivation.
- CSV, printable HTML, and SVG-oriented export support.
- Docker Compose runtime.
- Ollama LAN AI colleague configuration.
- Config-as-code for metadata, access control, quality, DPP, runtime, and AI integration.

## 7. Repository Structure

```text
product-layer/
  app/
    app.py                         Product-layer API, UI, sync, DPP, validation logic
  config/
    access_control.json            RBAC, ABAC, row-level security, masking, layer access
    ai_integration.json            AI colleague registry, default Ollama LAN provider
    dpp_schema.json                Digital Product Passport schema and access model
    metadata_schema.json           Data product metadata and identity contract
    quality_rules.json             Product quality rules and identity requirements
    runtime.json                   Service, data-layer, sync, and Ollama runtime defaults
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
  README.md                        Current official README
  readme_draft.md                  This proposal
```

## 8. Run Locally

From `product-layer`:

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

## 9. Run With Docker Compose

```bash
docker compose up --build
```

This starts:

- `product-layer` on `0.0.0.0:${PRODUCT_LAYER_PORT:-8080}`.
- `ollama` on `0.0.0.0:11434` for LAN access.

Use a different product-layer port:

```bash
PRODUCT_LAYER_PORT=8120 docker compose up --build
```

Ollama model downloads are intentionally manual:

```bash
docker compose exec ollama ollama pull gpt-oss:20b
```

## 10. AI Colleagues

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

Smoke test:

```bash
curl http://192.168.178.60:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss:20b","prompt":"Elaborate weather gradient for Stuttgart the next days.","stream":false}'
```

Governance rules:

- AI outputs are suggestions only.
- Human review is required before product data, metadata, DPP, certification, or quality state changes.
- Do not send personal, confidential, financial, customer, or protected telemetry data to an AI colleague unless the provider is approved for that classification.
- Central IT owns AI provider approval, network policy, logging policy, and model access policy.

## 11. Governance and Access Control

The product layer demonstrates governance controls locally through `config/access_control.json`.

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

Trusted role headers are ignored by default. For local privileged testing, configure `THEBEN_ROLE_TOKEN` or `THEBEN_TRUST_ROLE_HEADERS=true` and use a token-gated trusted role header:

```bash
curl -H "X-Role: ${THEBEN_TRUSTED_ROLE}" -H "X-Role-Token: ${THEBEN_ROLE_TOKEN}" http://127.0.0.1:8080/api/data-product
```

Production target:

- Replace token-gated local role headers with SSO/IAM claims.
- Enforce policies in platform security, governed SQL views, and APIs.
- Audit read, write, import, sync, export, and DPP access.
- Keep direct raw access limited to approved engineering, audit, and diagnostic use cases.

## 12. Metadata and Quality

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

## 13. Product Identity and Data Matrix

The product layer tracks the identifiers needed for a GS1 DataMatrix-style payload:

- `attributes.gtin`: Global Trade Item Number. Identical trade items from the same source should carry the same GTIN.
- `attributes.batch_lot_number`: production batch or lot for products sharing the same GTIN.
- `attributes.serial_number`: unique product instance identifier.

GTIN plus serial number is globally unique for a product instance.

The DPP/passport API derives:

```text
(01){gtin_14}(10){batch_lot_number}(21){serial_number}
```

## 14. Digital Product Passport

DPP configuration lives in:

```text
config/dpp_schema.json
```

The DPP module supports:

- Public, B2B, and authority-oriented access levels.
- Model, batch, and item granularity.
- Public DPP URL generation.
- Product identity.
- Origin.
- Materials and composition.
- Repairability and maintenance.
- End-of-life and recycling.
- Environmental performance.
- Compliance documentation.
- Service lifecycle data.
- Authority-only compliance data.

Endpoints:

```text
GET /dpp/{product-id}
GET /api/dpp/{product-id}?view=consumer|b2b|authority
GET /api/dpp/{product-id}/versions
GET /api/dpp/{product-id}/audit
GET /api/dpp/scan?code={public-url-or-structured-id}
```

Public DPP URLs are generated from `THEBEN_PUBLIC_BASE_URL` when set, otherwise from `config/runtime.json` `service.public_base_url`.

Keep the public base URL stable and HTTPS-ready because Data Matrix payloads may be printed on products and must not drift by caller host.

## 15. Data-Layer Integration

The current bridge uses the data-layer export endpoint:

```text
/api/v1/export/products.json
```

Local host example:

```bash
THEBEN_DATA_LAYER_SYNC_ENABLED=true \
THEBEN_DATA_LAYER_EXPORT_URL=http://127.0.0.1:8000/api/v1/export/products.json \
python3 -m app.app --host 127.0.0.1 --port 8080
```

Trigger sync:

```bash
curl -X POST -H "X-Role: ${THEBEN_TRUSTED_ROLE}" -H "X-Role-Token: ${THEBEN_ROLE_TOKEN}" http://127.0.0.1:8080/api/sync/data-layer
```

Docker Desktop for Mac default:

```text
http://host.docker.internal:8000/api/v1/export/products.json
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

The product-layer store auto-reloads the shared JSON file on reads by default:

```bash
THEBEN_STORE_AUTO_RELOAD=true
```

## 16. API Examples

List products:

```bash
curl http://127.0.0.1:8080/api/products?search=knx
```

Get summary:

```bash
curl http://127.0.0.1:8080/api/summary
```

Inspect data product catalog:

```bash
curl http://127.0.0.1:8080/api/catalog/data-products
```

Inspect role-aware data product surface:

```bash
curl http://127.0.0.1:8080/api/data-product
```

Inspect lineage:

```bash
curl http://127.0.0.1:8080/api/lineage
```

Inspect access policy:

```bash
curl http://127.0.0.1:8080/api/access-policy
```

Inspect data-layer integration:

```bash
curl http://127.0.0.1:8080/api/integrations/data-layer
```

Create a product:

```bash
curl -H "X-Role: ${THEBEN_TRUSTED_ROLE}" -H "X-Role-Token: ${THEBEN_ROLE_TOKEN}" -H 'Content-Type: application/json' \
  -d '{"sku":"THB-DEMO-1","name":"Demo","family":"Time Switch","attributes":{"gtin":"04003468999999","batch_lot_number":"LOT-2026-001","serial_number":"SN-0000000001","nominal_voltage":"230V","ip_rating":"IP20","co2_kg":1.2,"recyclable_share_pct":82}}' \
  http://127.0.0.1:8080/api/products
```

Read DPP views:

```bash
curl http://127.0.0.1:8080/api/dpp/thb-tim-0001?view=consumer
curl -H "X-Role: ${THEBEN_TRUSTED_ROLE}" -H "X-Role-Token: ${THEBEN_ROLE_TOKEN}" http://127.0.0.1:8080/api/dpp/thb-tim-0001?view=authority
curl http://127.0.0.1:8080/dpp/thb-tim-0001
```

## 17. Testing

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

Raw unit command:

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

Testing standard:

- Prefer `scripts/validate.sh all` before release notes or Mempalace loop documentation.
- Use `TEST_BASE_URL` for portable HTTP tests.
- Use Docker service names in containerized test profiles.
- Make Docker socket and context errors explicit instead of silently skipping container validation.

## 18. Consumption Channels

Approved product-layer consumption channels:

- Web UI for interactive product exploration.
- REST APIs for operational apps and integrations.
- OpenAPI JSON for generated clients and documentation.
- BI and analytics consumers through future governed views or semantic models.
- DPP HTML pages for public label scans.
- Controlled exports such as CSV, printable HTML, PDF-ready pages, and images where supported.
- Controlled external sharing only through approved interfaces.

Direct access to raw data should remain limited to approved engineering, audit, or diagnostic use cases.

## 19. Lifecycle and Change Management

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

## 20. Implementation Waves

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

- Manufacturing, finance, and advanced analytics integrations.
- Operational APIs.
- Controlled external sharing.
- Production-grade catalog, lineage, monitoring, and audit.

## 21. Production Readiness Checklist

Before production use, resolve or confirm:

- SSO/IAM integration replaces token-gated trusted role headers.
- TLS reverse proxy is configured.
- Firewall rules are reviewed for product-layer and Ollama ports.
- Persistent volumes have backup and restore procedures.
- GitHub CI runs unit, live, Docker, and contract tests.
- OpenMetadata publication is planned or implemented.
- Apache Iceberg target table and Trino access path are defined.
- Data-layer export contract is versioned.
- Access policies are enforced centrally and at consumption interfaces.
- Audit logging covers reads, writes, imports, syncs, exports, and DPP access.
- Mempalace documentation loops are used for decisions, learnings, incidents, and release notes.
- Central IT approves security, backup, monitoring, patching, and production readiness.

## 22. Key Config Files

| File | Purpose |
| --- | --- |
| `config/metadata_schema.json` | Data product definition, mandatory metadata, lineage, identity, lifecycle |
| `config/quality_rules.json` | Required attributes, Data Matrix identity policy, numeric ranges, certification policy |
| `config/access_control.json` | RBAC, ABAC, row-level security, masking, layer access |
| `config/dpp_schema.json` | DPP tiers, granularity, access levels, data carrier rules |
| `config/runtime.json` | Service defaults, public base URL, data-layer contract, sync config, Ollama defaults |
| `config/ai_integration.json` | AI colleague provider registry and governance policy |

## 23. Success Criteria

The product layer is successful when it:

- Provides a useful local product data experience.
- Shows how a curated product data product works in the lakehouse architecture.
- Keeps ownership, metadata, lineage, access, quality, and certification visible.
- Supports both human UI workflows and API consumers.
- Demonstrates DPP and Data Matrix readiness.
- Integrates cleanly with the data-layer without coupling to raw ingestion internals.
- Runs reproducibly with Docker Compose.
- Can be validated locally, in Docker, and in CI with the same test strategy.
- Can evolve from JSON adapter to Apache Iceberg-backed curated data product without breaking the business-facing product-layer contract.
