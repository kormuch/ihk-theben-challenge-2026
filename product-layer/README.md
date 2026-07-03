# Thebenpaul Product Layer

Local stdlib MVP for the product-layer part of the IHK Theben Challenge 2026.

## Run locally

```bash
python3 -m app.app --host 127.0.0.1 --port 8080
```

Open:

- Web UI: <http://127.0.0.1:8080/>
- API docs: <http://127.0.0.1:8080/docs>
- OpenAPI JSON: <http://127.0.0.1:8080/api/openapi.json>

The first run creates `data/products.json` with 1000 generated products.

## Docker Compose

```bash
docker compose up --build
```

This starts:

- `product-layer` on `0.0.0.0:${PRODUCT_LAYER_PORT:-8080}`.
- `ollama` on `0.0.0.0:11434` for LAN access.

Ollama model downloads are intentionally manual because the local validation path avoids external network installs:

```bash
docker compose exec ollama ollama pull gpt-oss:20b
```

AI colleague defaults live in `config/ai_integration.json`. The default provider is Ollama over LAN at `http://192.168.178.35:11434` with model `gpt-oss:20b`.

Smoke-test the configured provider from your LAN:

```bash
curl http://192.168.178.35:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss:20b","prompt":"Elaborate weather gradient for Stuttgart the next days.","stream":false}'
```

## API examples

```bash
curl http://127.0.0.1:8080/api/products?search=knx
curl -H 'X-Role: steward' http://127.0.0.1:8080/api/summary
curl http://127.0.0.1:8080/api/catalog/data-products
curl -H 'X-Role: steward' http://127.0.0.1:8080/api/data-product
curl http://127.0.0.1:8080/api/lineage
curl -H 'X-Role: steward' http://127.0.0.1:8080/api/access-policy
curl http://127.0.0.1:8080/api/integrations/data-layer
curl -H 'X-Role: editor' -H 'Content-Type: application/json' \
  -d '{"sku":"THB-DEMO-1","name":"Demo","family":"Time Switch","attributes":{"gtin":"04003468999999","batch_lot_number":"LOT-2026-001","serial_number":"SN-0000000001","nominal_voltage":"230V","ip_rating":"IP20","co2_kg":1.2,"recyclable_share_pct":82}}' \
  http://127.0.0.1:8080/api/products
curl http://127.0.0.1:8080/api/dpp/thb-tim-0001?view=consumer
curl -H 'X-Role: steward' http://127.0.0.1:8080/api/dpp/thb-tim-0001?view=authority
curl http://127.0.0.1:8080/dpp/thb-tim-0001
```

## Data Matrix identity

Product-layer tracks the identifiers needed for a GS1 DataMatrix-style payload:

- `attributes.gtin`: Global Trade Item Number for the trade item. Identical trade items from the same source use the same GTIN.
- `attributes.batch_lot_number`: production batch or lot for products sharing the same GTIN.
- `attributes.serial_number`: unique product instance identifier. GTIN plus serial number is globally unique.

The DPP/passport API derives:

```text
(01){gtin_14}(10){batch_lot_number}(21){serial_number}
```

The DPP module exposes:

- `/dpp/{product-id}`: public no-login HTML view for label scans.
- `/api/dpp/{product-id}?view=consumer|b2b|authority`: role-filtered DPP JSON.
- `/api/dpp/{product-id}/versions`: DPP lifecycle/version metadata.
- `/api/dpp/{product-id}/audit`: authority-only audit surface.
- `/api/dpp/scan?code={public-url-or-structured-id}`: resolve Data Matrix content.

Synchronize from the PAUL data-layer export contract:

```bash
THEBEN_DATA_LAYER_SYNC_ENABLED=true \
THEBEN_DATA_LAYER_EXPORT_URL=http://127.0.0.1:8000/api/v1/export/products.json \
python3 -m app.app --host 127.0.0.1 --port 8080

curl -X POST -H 'X-Role: editor' http://127.0.0.1:8080/api/sync/data-layer
```

### Debug data-layer to product-layer flow

Data-layer confirmation/export writes the product-layer-shaped payload to `product-layer/data/products.json` when `PRODUCT_LAYER_DATA_DIR` is mounted. Product-layer also exposes an explicit pull sync at `/api/sync/data-layer`.

The product-layer store auto-reloads the shared JSON file on reads by default:

```bash
THEBEN_STORE_AUTO_RELOAD=true
```

Use the flow debugger to check the bridge:

```bash
./scripts/debug-data-flow.sh
```

That checks the data-layer export endpoint, the shared `products.json` file, the product-layer sync contract, and the products visible through the product-layer API.

To also trigger the product-layer pull sync:

```bash
./scripts/debug-data-flow.sh --sync
```

Override endpoints when needed:

```bash
DATA_EXPORT_URL=http://127.0.0.1:8000/api/v1/export/products.json \
PRODUCT_URL=http://127.0.0.1:8080 \
./scripts/debug-data-flow.sh --sync
```

## Tests

Use the project validation runner so local, Docker, and CI checks stay aligned:

```bash
scripts/validate.sh all
```

Modes:

- `scripts/validate.sh unit`: sandbox-friendly unit/parser/model checks. Live HTTP tests are skipped.
- `scripts/validate.sh live`: run the suite against `TEST_BASE_URL`, defaulting to `http://127.0.0.1:8080`.
- `scripts/validate.sh docker`: rebuild product-layer, run host-to-container HTTP tests, then run the Compose `test` profile against `http://product-layer:8080`.
- `scripts/validate.sh all`: run `unit`, then `docker`. Use this before release notes or Mempalace loop documentation.

If Docker Desktop is running but the command says Docker is unreachable, run it from a terminal/session with Docker socket access. The script prints the active Docker context/socket to make that failure explicit instead of silently skipping container validation.

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

Public DPP URLs are generated from `THEBEN_PUBLIC_BASE_URL` when set, otherwise from `config/runtime.json` `service.public_base_url`. Keep this value stable and HTTPS because the Data Matrix payload is printed on products and must not drift per caller host.

## Integration contracts

The current store is a JSON adapter so the MVP runs locally. The target integration is:

`data-layer normalized store -> Apache Iceberg standardized table -> Apache Iceberg curated product data product -> product-layer REST/UI/export`

The current executable bridge uses the data-layer endpoint `/api/v1/export/products.json`, which already emits product-layer-shaped data. Configure it with `THEBEN_DATA_LAYER_EXPORT_URL`; Docker Compose defaults the URL to `http://host.docker.internal:8000/api/v1/export/products.json` for Docker Desktop on Mac, while local host runs can point at `127.0.0.1`. The sync records upstream schema version, export timestamp, domain module, lakehouse layer, and import errors in `sync_state`.

Governance endpoints:

- `/api/catalog/data-products`: domain-owned data product definition, mandatory metadata, target Iceberg table, and approved interfaces.
- `/api/data-product`: access-aware data product surface with sync state, interfaces, mandatory metadata, and caller permissions.
- `/api/lineage`: raw -> standardized -> curated -> consumption lakehouse path with layer ownership and access rules.
- `/api/access-policy`: RBAC, ABAC attributes, row-level security, masking, layer access, and caller-effective permissions.
- `/api/integrations/data-layer`: active data-layer export contract and sync settings.
- `/api/sync/data-layer`: GET sync configuration/state or POST a data-layer import refresh.

See `docs/architecture.md` and the JSON definitions under `config/`.
