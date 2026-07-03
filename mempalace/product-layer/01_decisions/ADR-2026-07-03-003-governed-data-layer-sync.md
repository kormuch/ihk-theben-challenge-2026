# ADR-2026-07-03-003 - Governed data-layer sync into product-layer

## Context
`Thebenpaul/goal.md` requires a central lakehouse backbone with domain modules, governed metadata, data products, access controls, and approved consumption interfaces. The data-layer already exposes `/api/v1/export/products.json`, which maps PAUL normalized products into the product-layer schema.

## Decision
Product-layer consumes the data-layer export as a governed upstream interface through `POST /api/sync/data-layer`. The sync source is configuration-driven by `THEBEN_DATA_LAYER_EXPORT_URL` or `config/runtime.json`, not request-body driven. Synced records are enriched with upstream export metadata, contract version, lakehouse layer, data product name, and target Apache Iceberg table.

For the local Docker-first development loop, product-layer also auto-reloads `data/products.json` on reads when the file mtime changes. This lets the data-layer best-effort shared-file export show up in product-layer without a service restart. The explicit `POST /api/sync/data-layer` path remains the governed API sync and audit path.

## Alternatives considered
- Keep product-layer as a local JSON-only mock.
- Let callers pass arbitrary sync URLs per request.
- Edit data-layer directly from product-layer.

## Rationale
The configured adapter keeps product-layer aligned with the lakehouse architecture while remaining Docker-first and locally runnable. It uses the data-layer interface without coupling product-layer to data-layer internals, and avoids an SSRF-style access-control gap by rejecting non-allowlisted hosts.

## Impact
Product-layer now exposes:

- `/api/sync/data-layer`
- `/api/integrations/data-layer`
- `/api/catalog/data-products`
- `/api/data-product`
- `/api/lineage`
- `/api/access-policy`

Data-layer remains the standardized upstream module. Product-layer remains the curated product domain/consumption module.

The debug entry point is `product-layer/scripts/debug-data-flow.sh`, which checks the data-layer export, shared JSON file, product-layer sync contract, and product-layer visible API count. With `--sync`, it triggers the governed pull sync.

## Related links
- GitHub issue:
- GitHub PR:
- Related pages:
  - `product-layer/06_quality-runs/QR-2026-07-03-002-product-layer-data-layer-sync-validation.md`
  - `product-layer/05_releases/REL-2026-07-03-002-product-layer-data-layer-sync.md`

## Tags
- product-layer
- data-layer
- governance
- metadata
- access-control
