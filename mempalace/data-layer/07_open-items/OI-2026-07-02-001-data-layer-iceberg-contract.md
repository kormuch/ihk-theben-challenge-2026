# OI-2026-07-02-001 - Data-layer Iceberg contract is not implemented yet

## Why open
The product-layer MVP documents the target flow into Apache Iceberg curated product data products, but data-layer currently has no ingestion, normalization, Iceberg table, or OpenMetadata lineage implementation.

## Next step
Implement the data-layer ingestion and normalization contract, then publish a curated product table compatible with `product-layer/config/metadata_schema.json`.

## Owner
Data-layer owner.

## Blocking factors
Data-layer implementation scope, source sample definitions, storage choice, and Iceberg/Trino/OpenMetadata runtime availability need to be completed.

## Related links
- GitHub issue:
- GitHub PR:
- Related notes:
  - `mempalace/data-layer/01_decisions/ADR-2026-07-02-002-data-layer-product-layer-contract.md`
  - `product-layer/docs/architecture.md`
