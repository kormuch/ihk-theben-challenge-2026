# REL-2026-07-03-002 - 0.2.0 - Product-layer data-layer sync and governance surface

## Released on
2026-07-03 in local development.

## What changed
- Added governed sync from the PAUL data-layer export contract into product-layer.
- Added catalog, data product, lineage, data-layer integration, and access-policy endpoints.
- Added a UI lakehouse interface panel for the data-layer contract and curated product data product.
- Added sync state persistence to the local JSON adapter.
- Added allowed-host validation for the configured upstream sync URL.

## Affected areas
- Product layer
- Data layer
- Tests
- Metadata
- Access control

## Verification
Passed:

- `python3 -B -m unittest discover -s tests -v`
- `docker compose --profile test config`
- `PYTHONPYCACHEPREFIX=/private/tmp/thebenpaul-pycache python3 -m py_compile app/app.py tests/test_app.py`
- Validation-agent second pass with no blocking findings.

Remains open:

- Live HTTP validation from the Codex sandbox is blocked by socket permissions.
- Apache Iceberg, Trino, OpenMetadata, and Airflow remain target architecture contracts, not executable integrations in this product-layer increment.

## Known limitations
The implemented sync covers the product domain only. Other goal domains remain architectural modules for future waves.

Access control remains header-driven for the local MVP; production requires SSO/IAM claims, audit logging, and platform-enforced policies.

## Related links
- GitHub release/tag:
- GitHub PRs:
- Quality run:
  - `product-layer/06_quality-runs/QR-2026-07-03-002-product-layer-data-layer-sync-validation.md`
