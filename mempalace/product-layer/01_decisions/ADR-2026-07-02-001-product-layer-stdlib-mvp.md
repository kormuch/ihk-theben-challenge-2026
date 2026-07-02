# ADR-2026-07-02-001 - Product-layer stdlib MVP with explicit lakehouse contracts

## Context
The product-layer needed an executable first implementation aligned with `Thebenpaul/goal.md`, while remaining local, Docker-first, open source first, and runnable without external package downloads.

## Decision
Implement the product-layer MVP as a Python standard-library REST and static UI service under `product-layer/`, with JSON-file persistence for local execution and explicit contracts for future Apache Iceberg, Trino, OpenMetadata, and data-layer integration.

## Alternatives considered
- Full framework service with FastAPI or similar dependencies
- Frontend-only static prototype
- Wait for data-layer/Iceberg implementation before building product-layer

## Rationale
The stdlib service validates the product-layer behavior immediately, avoids network dependency installation, and keeps the implementation generic, informative, interactive, and Docker Compose friendly. It also makes the boundary to the target lakehouse architecture explicit instead of hiding it.

## Impact
Product-layer now contains API, UI, OpenAPI JSON, export helpers, governance config, quality rules, Docker Compose runtime, and tests. Data-layer remains read-only and is represented through documented integration contracts.

## Related links
- GitHub issue:
- GitHub PR:
- Related pages:
  - `product-layer/README.md`
  - `product-layer/docs/architecture.md`
  - `product-layer/config/metadata_schema.json`

## Tags
- product-layer
- data-layer
- governance
- metadata
- access-control
