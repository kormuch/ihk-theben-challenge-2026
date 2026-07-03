# OI-2026-07-03-002 - DPP production hardening remains open

## Why open
The product-layer DPP MVP now satisfies the reviewed P1 runtime gaps, but several production and architecture items remain outside the current product-layer bugfix scope.

Open items:
- Replace local header/token role selection with production SSO/IAM claims.
- Terminate HTTPS through a production reverse proxy and define certificate operations.
- Generate and verify actual Data Matrix symbols, not only URI and GS1 payload metadata.
- Add multilingual DPP rendering using the configured `en` and `de` language set.
- Add an optional Ollama LAN reachability validation that does not break offline CI.
- Complete data-layer Iceberg, Trino, OpenMetadata, and lineage implementation.
- Decide whether to migrate Mempalace folders from current `product-layer` and `data-layer` to the `01_product-layer` and `02_data-layer` convention named in `goal.md`.

## Next step
Prioritize production hardening after the next architecture review. Keep these items as separate implementation waves rather than mixing them with DPP MVP bugfixes.

## Owner
Central IT/data platform for IAM, TLS, observability, catalog, and runtime operations. Product domain for DPP language content, symbol requirements, quality rules, and certification policy.

## Blocking factors
Production IAM/TLS decisions, registry/Data Matrix technical standard finalization, data-layer platform runtime availability, and Mempalace taxonomy decision.

## Related links
- GitHub issue:
- GitHub PR:
- Related notes:
  - `mempalace/product-layer/06_quality-runs/QR-2026-07-03-006-dpp-goal-bugfix-validation.md`
  - `mempalace/product-layer/05_releases/REL-2026-07-03-004-dpp-goal-bugfixes.md`
  - `mempalace/data-layer/07_open-items/OI-2026-07-02-001-data-layer-iceberg-contract.md`
