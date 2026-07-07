# PAUL — Product Attribute Unified Layer

**Event:** Kollege Codex — IHK Innovationstage Zollernalb | Mi, 08. Juli 2026, 13:00 Uhr
**Ort:** Theben AG, Haigerloch
**Team:** Korbinian Much + Christian Solva

---

## Problem

Produktinformationen bei Theben sind über zahlreiche Systeme und Formate verteilt:
- ERP, PLM, externe Portale, Datenbanken
- CSV, XLSX, JSON, XML, PDF, Bilder (PNG, JPG, …), REST APIs
- Dokumente von Produktmanagern, Laboren (Prüfberichte), Tickets, Marketing

**Kern-Pain-Point:** Kein Single Source of Truth → kein verlässlicher Digitaler Produktpass möglich.

Zusätzliche Anforderungsbereiche:
- Analytics & Reporting (Compliance, KPIs)
- Cybersecurity (CRA, SBOM)
- Umwelt & Nachhaltigkeit (CO₂, Materialien, Recycling)
- Normen & Zertifizierungen (IEC/EN, CE, UL)
- Regulatorik (CRA, RED, RoHS, REACH, ESPR, Data Act)
- Lebenszyklus (Einführung, Service Life, End-of-Life)

---

## Challenge

Skalierbare, erweiterbare Plattform die:

- Produktdaten aus heterogenen Quellen einsammelt
- Daten normalisiert und harmonisiert (gemeinsames Datenmodell)
- Vielzahl von Produktattributen trackt
- Mehrere Produktfamilien mit unterschiedlichen Eigenschaften unterstützt
- Flexibles Datenmodell hat das mit neuen Regularien mitwächst
- Querying, Reporting, Analytics ermöglicht
- Als Fundament für Digitalen Produktpass dient
- Interaktives Web-UI bietet (suchen, filtern, bearbeiten, validieren, visualisieren)

**Schlagworte:** Abstraction — Generic — Informative — Interactive

---

## Lösung: PAUL

PAUL ingests heterogeneous product data files (datasheets, lab reports, certificates, catalogs, etc.), uses AI to classify and extract structured product information, and lets users review and confirm before persisting. It serves as the data foundation for Digital Product Passports.

### How It Works

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
- **Multi-source detection**: Flags same article number found in multiple files during bulk upload, data is merged on confirm
- **LLM provider chain**: Ollama LAN (default), DeepSeek, Gemini, Groq — config-driven fallback
- **OCR support**: Images (PNG, JPG, TIFF, BMP, WEBP) and scanned PDFs via Tesseract OCR (deu+eng)
- **Bulk upload**: Multiple files at once, serialized processing with rate-limit awareness
- **Article number validation**: Import blocked until article number is provided for every product
- **AI transparency**: Full prompt visibility via `GET /api/v1/analyze/prompts` and transparency endpoints
- **Lakehouse sync**: Confirmed products are automatically mirrored to Apache Iceberg tables
- **Product-Layer sync**: Auto-export on confirm with retry + exponential backoff

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

---

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
        text_extract.py       # File-to-text (PDF, CSV, JSON, XML, XLSX, TXT, images via OCR)
      lakehouse/
        iceberg_writer.py     # Write products + lineage to Iceberg via Trino
      models/
        product.py            # Product, ProductFamily, ProductDocument
      seed/
        families.py           # 5 product families (Timer, Motion Sensor, Room Thermostat, KNX Actuator, Energy Meter)
        seed.py               # Auto-seeds families on startup
      core/
        config.py             # Settings
        database.py           # PostgreSQL connection
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
| Text extraction | pdfplumber, openpyxl, pytesseract + Pillow (OCR) |
| OCR Engine | Tesseract (deu + eng) |

---

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
| GET | `/api/v1/ingest/documents/{id}/download` | Download original uploaded file |
| GET | `/api/v1/analyze/prompts` | AI pipeline transparency (prompts, model, config) |
| GET | `/api/v1/lakehouse/health` | Trino/Iceberg status |
| GET | `/api/v1/lakehouse/products` | Query Iceberg product_master |

---

## Supported File Formats

| Format | Method | Notes |
|--------|--------|-------|
| PDF | pdfplumber | Text + Tabellen; OCR-Fallback für Scans |
| PNG, JPG, TIFF, BMP, WEBP | pytesseract OCR | Deutsch + Englisch |
| CSV, TSV | csv module | Pipe-separated output |
| XLSX, XLS | openpyxl | Alle Sheets, normalisierte Header |
| JSON | json module | Pretty-print, Fallback auf raw text |
| XML | ElementTree | Raw UTF-8 |
| TXT, MD, LOG | Direct read | UTF-8 mit error replace |

---

## Document Types (AI Classification)

Datasheet, Lab Report, Certificate, Software Documentation, Bill of Materials, Marketing Material, Compliance Declaration, Safety Data Sheet, Product Specification, Test Report

---

## Constraints

- Docker Compose (containerisierte Lösung)
- Persistenter Storage (Daten überleben Container-Restart)
- Keine zwingend externen Cloud-Services (lokal/Docker bevorzugt)
- Open-Source Tech-Stack
- Konfiguration über Config-Files und/oder Umgebungsvariablen

---

## Test Documents

The `data-layer/test-docs/hard/` folder contains realistic Theben-style test files including edge cases:

| File | Challenge |
|------|-----------|
| `01_messy_email_thread.txt` | German email with corrections, 2 products buried in prose |
| `02_ambiguous_brochure.txt` | Marketing fluff mixed with real specs |
| `03_unknown_product_type.xml` | KNX Gateway — doesn't fit existing families |
| `04_conflicting_data.csv` | Same product from 5 sources with contradicting values |
| `05_multi_family_mixed.json` | 7 products across 4+ families (SAP export) |
| `06_nearly_empty.txt` | Only 4 lines of data |
