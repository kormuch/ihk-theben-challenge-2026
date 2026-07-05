# Thebenpaul Data Layer

## Lakehouse Architecture

The data layer runs a full local lakehouse stack:

```
Document Upload → AI Classify/Extract → PostgreSQL (primary)
                                              ↓
                                     Iceberg product_master (via Trino)
                                              ↓
                                     Parquet files on MinIO (S3-compatible)
                                              ↓
                                     OpenMetadata (catalog, lineage, quality)
```

### Services

| Service | Port | Purpose |
|---------|------|---------|
| PostgreSQL 16 | 5432 | Primary product database |
| FastAPI Backend | 8000 | API, AI pipeline, Iceberg sync |
| React Frontend | 3000 | PAUL UI |
| MinIO | 9000/9001 | S3-compatible object storage for Iceberg |
| Iceberg REST Catalog | 8181 | Apache Iceberg table catalog |
| Trino | 8082 | SQL query engine for Iceberg tables |
| OpenMetadata | 8585 | Data catalog, lineage, governance |
| Elasticsearch | 9200 | OpenMetadata search backend |
| MySQL | 3306 | OpenMetadata metadata store |

### Quick Start

```bash
# Full stack including OpenMetadata
docker compose --profile openmetadata up -d --build

# Core only (without OpenMetadata)
docker compose up -d --build
```

Or use `start-paul.bat` from the project root for one-click startup.

### Iceberg Tables

Created automatically on first startup via `init/iceberg-init.sql`:

**`iceberg.products.product_master`** — Normalized product data, partitioned by family:
- article_number, product_name, family
- nominal_voltage, ip_rating, certifications
- attributes (JSON), source_system, lineage, owner, classification
- created_at, updated_at, ingested_at

**`iceberg.products.document_lineage`** — Document-to-product traceability:
- document_id, product_article_number, original_filename
- doc_type, source_uri, classification_confidence
- ingested_by, ingested_at

### Iceberg Sync

Products are mirrored to Iceberg automatically:
- On **confirm** (after AI extraction review)
- On **export** (product-layer sync)

The sync is non-blocking — if Trino is unreachable, PostgreSQL continues to work normally.

### Lakehouse API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/lakehouse/health` | Trino/Iceberg connectivity check |
| GET | `/api/v1/lakehouse/products` | Query Iceberg product_master via Trino |

### Direct Trino SQL

```bash
docker exec data-layer-trino-1 trino --execute \
  "SELECT article_number, product_name, family, certifications FROM iceberg.products.product_master"
```

### MinIO Console

http://localhost:9001 — Login: admin / password

Browse the `lakehouse` bucket to see Parquet files written by Iceberg.

### OpenMetadata

http://localhost:8585 — Login: admin / admin

Use it to:
- Browse the Iceberg tables as data assets
- View lineage (document → ingestion → Iceberg table → export)
- Set data quality rules and ownership
- Tag datasets with classification labels

Started via `--profile openmetadata`. Requires ~2 GB additional RAM.

---

## LLM Agent Configuration

Document analysis uses config-as-code from:

```bash
config/llm_agents.json
```

The backend reads this path from `DATA_LAYER_LLM_CONFIG`. In Docker Compose it is mounted read-only at `/config/llm_agents.json`.

By default, the data layer uses the same LAN Ollama pattern as the product layer:

```bash
DATA_LAYER_LLM_CHAIN=local_ollama_lan
```

Available chains:

- `local_ollama_lan`: Ollama LAN only (default)
- `analysis_default`: alias for Ollama LAN only
- `local_only`: backwards-compatible alias
- `enterprise_deepseek_existing`: DeepSeek only
- `enterprise_cloud_fallback`: Ollama LAN first, then cloud fallbacks
- `certification_expert`: certification-specific model first, then fallback

Secrets stay in environment variables (`.env`, Docker secrets, or CI secrets):

```bash
OLLAMA_API_KEY=
OLLAMA_CERTIFICATION_API_KEY=
DEEPSEEK_API_KEY=
GEMINI_API_KEY=
GROQ_API_KEY=
```

## Architecture

```
data-layer/
  backend/
    app/
      api/              # REST endpoints (analyze, products, families, ingest, export)
      intelligence/     # AI pipeline (classifier, extractors, LLM provider chain)
      lakehouse/        # Iceberg writer (Trino-based, non-blocking)
      models/           # SQLAlchemy models (Product, ProductFamily, ProductDocument)
      seed/             # Auto-seed product families on startup
      core/             # Config, database connection
  frontend/             # React + Vite + Tailwind CSS
  config/               # LLM agent config (llm_agents.json)
  trino/catalog/        # Trino catalog properties (Iceberg connector)
  init/                 # Iceberg table init SQL
  storage/              # Uploaded document originals
  docker-compose.yml    # Full stack definition
```
