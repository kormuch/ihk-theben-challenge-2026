# Theben Layer

The `theben-layer` is the branded competition and reporting layer for Thebenpaul. It connects to the proprietary REST system, gathers product compliance data, generates SBOM and VEX artifacts, and produces a Theben-styled PDF report using the provided Theben logo asset.

## Architecture

```text
proprietary REST system
        |
        v
theben-layer extraction
        |
        +--> CycloneDX SBOM
        +--> CSAF/VEX-style overview
        +--> Theben-styled PDF / HTML preview
        |
        v
data-layer/product-layer/graph-layer/agent-layer consumption
```

## Runtime Principles

- The proprietary REST system remains the source for the competition add-on data.
- The data-layer imports product records through a visible button/action.
- Theben-layer stores derived report artifacts locally and keeps source metadata.
- API discovery is bounded, read-only, low-rate, and limited to the authorized host.
- The PDF uses `assets/logo_theben.jpg`, copied from the user-provided logo in `99_shared/logo_theben.jpg`.

## Quick Start

```bash
cd theben-layer
docker compose up --build
```

Health check:

```bash
curl http://localhost:8098/health
```

Generate a report:

```bash
curl -X POST http://localhost:8098/api/theben/reports \
  -H "Content-Type: application/json" \
  -d '{"use_fixtures":true}'
```

Generate from CLI:

```bash
python3 -B -m app.app --generate-report --fixtures
```

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service and brand asset status |
| `GET` | `/api/theben/products` | Product list normalized from legacy data |
| `POST` | `/api/theben/extract` | Extract data and write artifacts |
| `POST` | `/api/theben/reports` | Generate report artifacts |
| `GET` | `/api/theben/reports/{report_id}` | Report JSON |
| `GET` | `/api/theben/reports/{report_id}/pdf` | PDF report |
| `GET` | `/api/theben/reports/{report_id}/preview` | HTML preview |

## Configuration

Runtime configuration lives in `config/runtime.json`.

Important environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `THEBEN_LEGACY_BASE_URL` | `http://192.168.8.200:8000` | Proprietary REST system |
| `THEBEN_LAYER_DATA_DIR` | `theben-layer/data` | Report artifact storage |
| `THEBEN_LOGO_PATH` | `theben-layer/assets/logo_theben.jpg` | PDF logo source |
| `THEBEN_USE_FIXTURES` | `true` | Fallback when legacy host is unavailable |

## Validation

```bash
cd theben-layer
sh scripts/validate.sh
```

The tests validate product normalization, fixture extraction, SBOM generation, VEX generation, and PDF artifact creation.
