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

## Domain-owned data product

The initial data product is `product-master-dpp`:

- Domain: product.
- Owner: Product Data Domain.
- Steward: product-data-steward@thebenpaul.local.
- Purpose: governed product information and Digital Product Passport preview.
- Consumers: product management, compliance, service, analytics, operational apps.
- Contract: see `config/metadata_schema.json`.

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
- Required generic and family-specific attributes.
- Numeric range sanity checks.

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

Operational TODOs before production:

- Central IT review for security, backup, monitoring, patching, and production readiness.
- Reverse proxy with TLS.
- Persistent volume backup policy.
- Firewall rules for ports `8080` and `11434`.
- Model pull and model access policy for Ollama.
- GitHub CI for tests, image build, and release tracking.
