# REL-2026-07-02-001 - 0.1.0 - Product-layer MVP

## Released on
2026-07-02, local Codex workspace and product-layer repo state.

## What changed
- Added executable product-layer REST API, OpenAPI JSON/docs endpoint, and static Web UI.
- Added product upload/import, overview, search/filter, attribute editing, validation status, summary visualization, and Digital Product Passport preview.
- Added CSV export, printable HTML/PDF-friendly export, SVG picture export, metadata/quality/access-control config, Docker Compose runtime, Ollama LAN service, and portable tests.

## Affected areas
- Product layer
- Data layer
- Tests
- Metadata
- Access control

## Verification
Passed:
- `python3 -B -m unittest discover -s tests -v`
- Result: 12 tests run, 9 passed, 3 live HTTP tests skipped because `TEST_BASE_URL` was not set.
- `docker compose --profile test config`

Open:
- Docker runtime test not executed because sandbox cannot access Docker Desktop socket.
- Context7 and my-mempalace MCP tools were not callable in this session.

## Known limitations
The MVP uses JSON-file persistence and documented Apache Iceberg/Trino/OpenMetadata target contracts. Header-based local auth demonstrates RBAC/ABAC concepts but does not replace SSO/IAM. Ollama LAN service is configured but not runtime-tested from this sandbox.

## Related links
- GitHub release/tag:
- GitHub PRs:
- Quality run:
  - `mempalace/product-layer/06_quality-runs/QR-2026-07-02-001-product-layer-local-validation.md`
