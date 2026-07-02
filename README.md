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
```

### Two-Stage AI Pipeline

1. **Classifier Agent** — Reads raw text, determines document type (10 known types), confidence score, reasoning, and detected products
2. **Extractor Agent** — Per-document-type specialized prompt extracts article numbers, names, attributes, and family suggestions. Every value includes a **citation** showing where in the source document it was found

### Smart Features

- **Confidence gate**: >= 85% auto-extracts, < 85% lets user pick/type document type and retry
- **Existing product diff**: Shows attribute-level changes (new, changed, kept) when a product already exists
- **Cross-file dedup**: Flags same article number found in multiple files during bulk upload
- **LLM fallback**: Gemini 2.0 Flash primary, Groq (Llama 3.3 70B) fallback with retry + backoff
- **Bulk upload**: Multiple files at once, serialized processing with rate-limit awareness

## Quick Start

**One-click start (Windows):**
```
start-paul.bat
```
This builds containers, waits for health check, opens the browser, and streams logs.

**Manual:**
```bash
cd data-layer
docker compose up -d --build
# Open http://localhost:3000
```

**Requirements:**
- Docker + Docker Compose
- `.env` file in `data-layer/` with API keys:
  ```
  GEMINI_API_KEY=your_key
  GROQ_API_KEY=your_key
  ```

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
      intelligence/
        llm.py                # LLM call layer (Gemini/Groq, retry, lock, fallback)
        classifier.py         # Stage 1: document type classification
        extractors.py         # Stage 2: per-type product data extraction
        text_extract.py       # File-to-text (PDF, CSV, JSON, XML, XLSX, TXT)
      models/
        product.py            # Product, ProductFamily, ProductDocument
      seed/
        families.py           # 3 product families (Timer, Motion Sensor, Room Thermostat)
        seed.py               # Auto-seeds families on startup
      core/
        config.py             # Settings
        database.py           # PostgreSQL connection
  frontend/                   # React + Vite + Tailwind CSS
    src/
      pages/
        UploadPage.tsx        # AI Ingest — drag & drop, bulk upload, review, confirm
        ProductsPage.tsx      # Product list with search, filter, create, delete
        ProductDetailPage.tsx # Product detail, attribute editor, document upload
        FamiliesPage.tsx      # Product family management
      components/
        Sidebar.tsx           # Navigation
      lib/
        api.ts                # API client
  test-docs/                  # Test documents for demo
    LUXA_200-360_Datasheet.csv
    LUXA_200-360_Lab_Report.txt
    LUXA_200-360_CE_Declaration.txt
    Multi_Product_Catalog.json
    hard/                     # Edge-case test documents
  docker-compose.yml          # PostgreSQL 16 + FastAPI + React
architecture.html             # Visual architecture diagram (open in browser)
start-paul.bat                # One-click start
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python, FastAPI, SQLAlchemy, uvicorn |
| Frontend | React, TypeScript, Vite, Tailwind CSS |
| Database | PostgreSQL 16 |
| AI / LLM | Gemini 2.0 Flash (primary), Groq Llama 3.3 70B (fallback) |
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
