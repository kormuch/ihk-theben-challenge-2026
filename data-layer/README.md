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

## OCR / Image support

The backend uses Tesseract OCR (via pytesseract + Pillow) for:
- **Image files** (PNG, JPG, TIFF, BMP, WEBP) — direct OCR text extraction
- **Scanned PDFs** — automatic OCR fallback when pdfplumber finds no text

Languages installed: German (`deu`) + English (`eng`).

The Dockerfile installs `tesseract-ocr`, `tesseract-ocr-deu`, and `tesseract-ocr-eng`. For local development outside Docker, install Tesseract separately:
- Windows: `winget install UB-Mannheim.TesseractOCR`
- macOS: `brew install tesseract tesseract-lang`
- Linux: `apt install tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng`

## Product-Layer export

The endpoint `GET /api/v1/export/products.json` exports all products in product-layer format (schema version `0.1.0`). It is automatically called when products are confirmed via `/api/v1/analyze/confirm` and writes to the shared volume at `PRODUCT_LAYER_DATA_DIR` (default: `/product-layer-data`).

Family mapping (data-layer -> product-layer):
- Timer -> Time Switch
- Motion Sensor -> Motion Detector
- Room Thermostat -> HVAC Controller
- KNX Actuator -> KNX Actuator
- Energy Meter -> Energy Meter

## Theben Proprietary REST Import

The Products page includes two Theben import actions:

- `Import Theben REST` imports products from `THEBEN_LEGACY_BASE_URL` (default `http://192.168.8.200:8000`).
- `Import Bundled Theben` imports the two bundled competition products from `config/theben_legacy_products`.

The REST import follows the verified proprietary API calls:

```bash
curl "http://192.168.8.200:8000/products"
curl "http://192.168.8.200:8000/products/bom?articlenumber=7654126"
```

During import, data-layer first reads `/products`, then calls `/products/bom?articlenumber={article}` for each imported article and stores the parsed XML BOM as governed product attributes.

Backend endpoints:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/legacy-theben/health` | Check data-layer backend connectivity to the proprietary REST system |
| GET | `/api/v1/legacy-theben/products` | List products from the proprietary REST system |
| POST | `/api/v1/legacy-theben/import-products` | Import or refresh products from the proprietary REST system |
| GET | `/api/v1/legacy-theben/bundled-products` | Preview bundled Theben products |
| POST | `/api/v1/legacy-theben/import-bundled-products` | Import or refresh bundled Theben products |

The bundled files currently contain article `7654126` and `8654126` with XML BOM content. Import stores BOM item count, categories, suppliers, parsed item details, source metadata, and lineage on the product attributes.

If host curl works but Docker import fails, test from the backend container:

```bash
docker exec -it data-layer-backend-1 curl -v http://192.168.8.200:8000/products
docker exec -it data-layer-backend-1 curl -v "http://192.168.8.200:8000/products/bom?articlenumber=7654126"
curl http://localhost:8000/api/v1/legacy-theben/health
```

The backend HTTP client ignores proxy environment variables for this LAN call (`httpx trust_env=false`), and Docker Compose sets `NO_PROXY` for the proprietary host.

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

`local_ollama_lan` uses the configured LAN Ollama URL:

```text
http://192.168.178.60:11434
```

Override the active Ollama route without editing JSON:

```bash
DATA_LAYER_OLLAMA_BASE_URL=http://192.168.178.60:11434
```

Available chains:

- `local_ollama_lan`: Ollama LAN host (default)
- `analysis_default`: alias for local Ollama analysis
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

Container-side connectivity check:

```bash
docker compose exec backend python - <<'PY'
import urllib.request
url = "http://192.168.178.60:11434/api/tags"
try:
    with urllib.request.urlopen(url, timeout=8) as response:
        print(url, response.status)
except Exception as exc:
    print(url, type(exc).__name__, exc)
PY
```

Failure interpretation:

- `192.168.178.60` fails with `ConnectError`: the Docker backend container cannot route to the LAN Ollama host. Check Docker Desktop networking, VPN/firewall rules, or the Ollama host firewall.
- If product-layer Docker is running, it must not publish a local Ollama service on host port `11434`. The product-layer Compose file keeps its local Ollama service behind the `local-ollama` profile and publishes it on `11435` by default.

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
