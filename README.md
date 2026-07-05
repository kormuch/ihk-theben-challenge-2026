# PAUL — Product Attribute Unified Layer

**Event:** Kollege Codex — IHK Innovationstage Zollernalb | Wed, July 8, 2026
**Company:** Theben AG, Haigerloch
**Team:** Korbinian Much + Christian Solva

## What is PAUL?

PAUL ingests heterogeneous product data files (datasheets, lab reports, certificates, catalogs, etc.), uses AI to classify and extract structured product information, and lets users review and confirm before persisting. It serves as the data foundation for Digital Product Passports.

## How It Works

```
Drop files  -->  AI Classifier  -->  AI Extractor  -->  Human Review  -->  Database
 (any format)   (document type)    (product data     (edit, confirm)    (create/update
                  + confidence)     + citations)                         products)
                                                                            |
                                                              Iceberg (Parquet on MinIO)
                                                                            |
                                                              OpenMetadata (lineage, catalog)
```

### Two-Stage AI Pipeline

1. **Classifier Agent** — Reads raw text, determines document type (10 known types), confidence score, reasoning, and detected products
2. **Extractor Agent** — Per-document-type specialized prompt extracts article numbers, names, attributes, and family suggestions. Every value includes a **citation** showing where in the source document it was found

### Smart Features

- **Confidence gate**: >= 85% auto-extracts, < 85% lets user pick/type document type and retry
- **Existing product diff**: Shows attribute-level changes (new, changed, kept) when a product already exists
- **Cross-file dedup**: Flags same article number found in multiple files during bulk upload
- **LLM provider chain**: Ollama LAN (default), DeepSeek, Gemini, Groq — config-driven fallback
- **Bulk upload**: Multiple files at once, serialized processing with rate-limit awareness
- **Lakehouse sync**: Confirmed products are automatically mirrored to Apache Iceberg tables

## Quick Start

**One-click start (Windows):**
```
start-paul.bat
```
Starts all services (data-layer, product-layer, lakehouse infrastructure, OpenMetadata), waits for health checks, opens browser, streams logs.

| Service | URL | Description |
|---------|-----|-------------|
| PAUL UI | http://localhost:3000 | AI Ingest, Products, Families |
| PAUL API | http://localhost:8000/docs | FastAPI Swagger docs |
| Product Layer | http://localhost:8080 | Governance, DPP preview, exports |
| Trino UI | http://localhost:8082 | SQL query engine for Iceberg |
| MinIO Console | http://localhost:9001 | Object storage browser (admin/password) |
| OpenMetadata | http://localhost:8585 | Data catalog & lineage (admin/admin) |
| Lakehouse Health | http://localhost:8000/api/v1/lakehouse/health | Trino/Iceberg status |
| Lakehouse Products | http://localhost:8000/api/v1/lakehouse/products | Query Iceberg tables |

**Manual:**
```bash
cd data-layer && docker compose --profile openmetadata up -d --build
cd ../product-layer && docker compose up -d --build product-layer
```

**Without OpenMetadata (lighter):**
```bash
cd data-layer && docker compose up -d --build
```

**Requirements:**
- Docker + Docker Compose
- ~4 GB RAM for full stack (or ~2 GB without OpenMetadata)
- `.env` file in `data-layer/` with LLM API keys (optional, defaults to Ollama LAN)

## Architecture

```
data-layer/
  backend/                    # FastAPI + SQLAlchemy
    app/
      api/
        analyze.py            # AI pipeline endpoints (upload, lookup, re-extract, confirm)
        families.py           # Product family CRUD
        products.py           # Product CRUD
        ingest.py             # Direct file upload to existing products
        export.py             # Export to product-layer + Iceberg sync
      intelligence/
        llm.py                # LLM provider chain (Ollama/DeepSeek/Gemini/Groq)
        classifier.py         # Stage 1: document type classification
        extractors.py         # Stage 2: per-type product data extraction
        text_extract.py       # File-to-text (PDF, CSV, JSON, XML, XLSX, TXT)
      lakehouse/
        iceberg_writer.py     # Write products + lineage to Iceberg via Trino
      models/
        product.py            # Product, ProductFamily, ProductDocument
      seed/                   # Auto-seeds families on startup
      core/                   # Settings, database connection
  frontend/                   # React + Vite + Tailwind CSS
  config/                     # LLM agent config (llm_agents.json)
  trino/catalog/              # Trino Iceberg connector config
  init/                       # Iceberg table creation SQL
  docker-compose.yml          # Full stack (DB, MinIO, Iceberg, Trino, OpenMetadata)
  test-docs/                  # Test documents for demo

product-layer/                # Christian's governance layer (DPP, validation, exports)
architecture.html             # Visual architecture diagram (open in browser)
start-paul.bat                # One-click start (all services)
```

## Lakehouse Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Object Storage | MinIO | S3-compatible, stores Parquet files |
| Table Format | Apache Iceberg | Versioned tables, schema evolution, time travel |
| Query Engine | Trino | SQL access to Iceberg tables |
| Data Catalog | OpenMetadata | Lineage, ownership, quality, classification |

Products confirmed through the AI pipeline are automatically mirrored to Iceberg `product_master` table. Document provenance is tracked in `document_lineage`. Both tables are queryable via Trino SQL.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python, FastAPI, SQLAlchemy, uvicorn |
| Frontend | React, TypeScript, Vite, Tailwind CSS |
| Database | PostgreSQL 16 |
| AI / LLM | Ollama LAN (default), DeepSeek, Gemini, Groq (config-driven) |
| Lakehouse | Apache Iceberg, Trino, MinIO |
| Data Catalog | OpenMetadata |
| Infrastructure | Docker Compose |
| Text extraction | pdfplumber, openpyxl |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/analyze/` | Upload file, classify, extract |
| POST | `/api/v1/analyze/lookup` | Check which article numbers exist |
| POST | `/api/v1/analyze/re-extract` | Re-extract with user-chosen doc type |
| POST | `/api/v1/analyze/confirm` | Confirm and persist extracted products |
| GET/POST | `/api/v1/families/` | List / create families |
| GET/POST | `/api/v1/products/` | List / create products |
| GET/PATCH/DELETE | `/api/v1/products/{id}` | Product detail / update / delete |
| POST | `/api/v1/ingest/upload` | Direct file upload to existing product |
| GET | `/api/v1/export/products.json` | Export to product-layer format |
| GET | `/api/v1/lakehouse/health` | Trino/Iceberg status |
| GET | `/api/v1/lakehouse/products` | Query Iceberg product_master |

## Document Types (AI Classification)

Datasheet, Lab Report, Certificate, Software Documentation, Bill of Materials, Marketing Material, Compliance Declaration, Safety Data Sheet, Product Specification, Test Report

## Test Documents

The `test-docs/` folder contains realistic Theben-style test files. The `test-docs/hard/` folder contains edge cases:

| File | Challenge |
|------|-----------|
| `01_messy_email_thread.txt` | German email with corrections, 2 products buried in prose |
| `02_ambiguous_brochure.txt` | Marketing fluff mixed with real specs |
| `03_unknown_product_type.xml` | KNX Gateway — doesn't fit existing families |
| `04_conflicting_data.csv` | Same product from 5 sources with contradicting values |
| `05_multi_family_mixed.json` | 7 products across 4+ families (SAP export) |
| `06_nearly_empty.txt` | Only 4 lines of data |
