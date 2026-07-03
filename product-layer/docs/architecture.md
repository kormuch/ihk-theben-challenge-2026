# Thebenpaul Product-Layer Architecture Notes

## MVP scope

This product-layer is an executable local MVP for the IHK challenge. It provides:

- REST API with `/api/openapi.json` and `/docs`.
- Static web UI for product overview, search/filter, import, attribute editing, validation/status, summary visualization, and Digital Product Passport preview.
- CSV, printable HTML, and SVG exports.
- Config-as-code for metadata, quality, runtime, lifecycle, RBAC, ABAC, row-level security, and masking.
- Docker Compose runtime with a product service and Ollama bound for LAN access.

The MVP uses a JSON file store so it can run without external installs. That store is an adapter boundary, not the target architecture.

## Target lakehouse direction

The target table format is Apache Iceberg. The product-layer should eventually read curated product data from Iceberg tables through governed SQL views or APIs, likely exposed by Trino. The intended flow is:

1. Data-layer ingests CSV, JSON, XML, XLSX, PDF, REST sources and stores original files with traceability.
2. Data-layer normalizes product records into a common model.
3. Standardized data lands in Iceberg tables.
4. Product domain owns curated Iceberg data products such as `curated_product.product_master_dpp`.
5. Product-layer consumes curated views/APIs and exposes stable REST/UI/export interfaces.

The current executable interface uses the data-layer export endpoint:

`/api/v1/export/products.json`

That endpoint maps PAUL data-layer products into the product-layer schema. Product-layer imports it through `POST /api/sync/data-layer`, controlled by `product:import`, and enriches each synced record with upstream export metadata, contract version, lakehouse layer, data product name, and target Iceberg table. The URL is configurable through `THEBEN_DATA_LAYER_EXPORT_URL`; implicit sync is enabled with `THEBEN_DATA_LAYER_SYNC_ENABLED=true`, so the same code can point at `127.0.0.1`, a Docker Compose service name, or a CI endpoint.

## Domain-owned data product

The initial data product is `product-master-dpp`:

- Domain: product.
- Owner: Product Data Domain.
- Steward: product-data-steward@thebenpaul.local.
- Purpose: governed product information and Digital Product Passport preview.
- Consumers: product management, compliance, service, analytics, operational apps.
- Contract: see `config/metadata_schema.json`.

Discoverable runtime endpoints:

- `/api/catalog/data-products`: data product definition and mandatory metadata.
- `/api/data-product`: access-aware data product surface, interfaces, sync state, and caller permissions.
- `/api/lineage`: raw, standardized, curated, and consumption layer model.
- `/api/access-policy`: RBAC, ABAC, row-level security, masking, and layer-access policy.
- `/api/integrations/data-layer`: configured data-layer interface.
- `/api/sync/data-layer`: governed sync from the standardized data-layer export into the curated product-layer adapter.
- `/dpp/{product-id}`: public, no-login EU DPP HTML view intended for label scans.
- `/api/dpp/{product-id}?view=consumer|b2b|authority`: role-filtered DPP record.
- `/api/dpp/{product-id}/versions`: lifecycle and version history.
- `/api/dpp/{product-id}/audit`: authority-only audit surface.
- `/api/dpp/scan?code=...`: Data Matrix URL or structured identifier resolver.

## Governance and access

The MVP implements local header-driven controls for demonstration:

- RBAC: `X-Role` supports `viewer`, `editor`, `steward`, and `admin`.
- ABAC placeholders: role, purpose, region, classification.
- Row-level security: regional products are filtered unless the role can read all regions.
- Masking: confidential commercial price attributes are masked unless the role can unmask them.
- Layer access definitions are codified for raw, standardized, curated, and consumption layers.

Production integration TODOs:

- Replace header role selection with SSO/IAM group claims.
- Enforce policies in the platform layer and in governed SQL views.
- Add audit logging for read/write/export actions.
- Add approval workflow for access to confidential, personal, financial, customer, and telemetry attributes.

## Metadata and quality

Mandatory metadata is defined in `config/metadata_schema.json` and checked by `config/quality_rules.json`. The validation endpoint checks:

- Required metadata.
- Required product identity fields for GS1 DataMatrix-style payloads: GTIN, batch/lot number, and serial number.
- Required generic and family-specific attributes.
- Numeric range sanity checks.

The product identity contract is:

- GTIN identifies the trade item. All identical trade items from the same source carry the same GTIN.
- Batch/lot number identifies a production batch of products sharing the same GTIN.
- Serial number uniquely identifies each product instance.
- GTIN plus serial number is globally unique for a product instance.
- Product-layer derives a Data Matrix payload using GS1 application identifiers `01`, `10`, and `21`.

Production integration TODOs:

- Publish metadata to OpenMetadata.
- Attach lineage from ingestion jobs and transformations.
- Promote quality checks to CI and scheduled platform jobs.
- Track data product version, release notes, deprecation windows, and incidents in GitHub and Mempalace.

## Local VM deployment shape

Run on a company-managed VM with Docker Compose:

```bash
cd product-layer
docker compose up --build
```

Services:

- `product-layer`: Python stdlib REST/UI service on `0.0.0.0:8080`.
- `ollama`: local LLM endpoint on `0.0.0.0:11434` for LAN access.

## Standard validation path

The project standard is to use `scripts/validate.sh` rather than hand-assembling test commands for each loop:

```bash
scripts/validate.sh all
```

`all` runs sandbox-friendly unit/parser/model checks, rebuilds the product-layer image, validates the host-mapped endpoint with `TEST_BASE_URL`, and runs the Docker Compose `test` profile against the service name `product-layer:8080`.

Use `scripts/validate.sh unit` when Docker socket access is intentionally unavailable, and use `scripts/validate.sh docker` for release, validation-agent, and Mempalace documentation loops. If Docker Desktop is running but the shell cannot reach the Docker API socket, the script fails with a clear Docker-context diagnostic instead of producing a misleading product-layer test failure.

AI colleague configuration is kept as code in `config/ai_integration.json`. The default provider is Ollama over LAN at `http://192.168.178.35:11434`, using `gpt-oss:20b`, with human review required for any product data, metadata, or certification-impacting output.

Optional integration:

- `THEBEN_DATA_LAYER_EXPORT_URL`: points product-layer sync at the data-layer export endpoint. The Compose default is `http://host.docker.internal:8000/api/v1/export/products.json` for Docker Desktop on Mac; host-local runs can use `http://127.0.0.1:8000/api/v1/export/products.json`.
- `THEBEN_DATA_LAYER_SYNC_ENABLED`: set to `true` to allow `POST /api/sync/data-layer` to use the configured URL without an explicit request body.

Operational TODOs before production:

- Central IT review for security, backup, monitoring, patching, and production readiness.
- Reverse proxy with TLS.
- Persistent volume backup policy.
- Firewall rules for ports `8080` and `11434`.
- Model pull and model access policy for Ollama.
- GitHub CI for tests, image build, and release tracking.
