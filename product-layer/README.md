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
docker compose exec ollama ollama pull llama3.2
```

## API examples

```bash
curl http://127.0.0.1:8080/api/products?search=knx
curl -H 'X-Role: steward' http://127.0.0.1:8080/api/summary
curl -H 'X-Role: editor' -H 'Content-Type: application/json' \
  -d '{"sku":"THB-DEMO-1","name":"Demo","family":"Time Switch","attributes":{"gtin":"4003468999999","nominal_voltage":"230V","ip_rating":"IP20","co2_kg":1.2,"recyclable_share_pct":82}}' \
  http://127.0.0.1:8080/api/products
```

## Tests

Local unit and parser/model tests are sandbox-friendly and skip live HTTP checks unless `TEST_BASE_URL` is set:

```bash
python3 -B -m unittest discover -s tests -v
```

Run the same suite against a local service:

```bash
python3 -m app.app --host 127.0.0.1 --port 8120
TEST_BASE_URL=http://127.0.0.1:8120 python3 -B -m unittest discover -s tests -v
```

Run the same suite in Docker/CI against the Compose service name:

```bash
docker compose --profile test up --build --abort-on-container-exit --exit-code-from test test
```

Use `PRODUCT_LAYER_PORT=8120` if the host already has something on `8080`.

## Integration contracts

The current store is a JSON adapter so the MVP runs locally. The target integration is:

`data-layer normalized store -> Apache Iceberg standardized table -> Apache Iceberg curated product data product -> product-layer REST/UI/export`

See `docs/architecture.md` and the JSON definitions under `config/`.
