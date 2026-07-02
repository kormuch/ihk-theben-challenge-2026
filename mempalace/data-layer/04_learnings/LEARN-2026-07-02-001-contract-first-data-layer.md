# LEARN-2026-07-02-001 - Contract-first data-layer work keeps product-layer unblocked

## Situation
Product-layer needed to progress before data-layer ingestion, normalization, Iceberg, Trino, and OpenMetadata runtime pieces were implemented.

## Lesson
A contract-first boundary lets product-layer build and validate UI/API/export behavior while data-layer evolves independently. The contract must still be explicit about metadata, lineage, certification status, ownership, and target Iceberg tables.

## Recommendation
Data-layer should implement against `product-layer/config/metadata_schema.json` and publish compatibility notes when normalized tables or curated Iceberg tables become available.

## Related links
- GitHub issue:
- GitHub PR:
- Incident or decision:
  - `mempalace/data-layer/01_decisions/ADR-2026-07-02-002-data-layer-product-layer-contract.md`
  - `mempalace/data-layer/07_open-items/OI-2026-07-02-001-data-layer-iceberg-contract.md`
