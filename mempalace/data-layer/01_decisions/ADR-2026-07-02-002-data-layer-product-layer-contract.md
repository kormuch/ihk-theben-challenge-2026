# ADR-2026-07-02-002 - Data-layer to product-layer contract uses curated product data products

## Context
The architecture goal requires a central lakehouse with domain-owned data products, mandatory metadata, lineage, quality rules, and governed consumption channels. The current implementation scope is product-layer, while data-layer remains a separate responsibility.

## Decision
Keep data-layer responsible for ingestion, normalization, original document traceability, and future Apache Iceberg standardized/curated tables. Product-layer consumes the curated product data product through REST/UI/export interfaces and documents a temporary JSON adapter for local MVP execution.

## Alternatives considered
- Product-layer owns ingestion and source normalization
- Product-layer reads raw files directly
- Data-layer waits until product-layer is complete before defining contracts

## Rationale
This separation keeps ownership clear: data-layer owns source ingestion and standardized data, product-layer owns governed consumption, interaction, preview, and export. It matches the goal's centralized platform with decentralized domain ownership.

## Impact
Data-layer is not modified by the product-layer MVP. Future data-layer work should publish metadata, lineage, quality status, and curated Iceberg tables that match the `product-master-dpp` contract.

## Related links
- GitHub issue:
- GitHub PR:
- Related pages:
  - `product-layer/config/metadata_schema.json`
  - `product-layer/docs/architecture.md`
  - `Thebenpaul/goal.md`

## Tags
- product-layer
- data-layer
- governance
- metadata
- access-control
