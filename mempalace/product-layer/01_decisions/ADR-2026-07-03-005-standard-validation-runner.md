# ADR-2026-07-03-005 - Standard validation runner for product-layer loops

## Context
Product-layer validation had drifted into several manual commands: unit tests, host-to-Docker live HTTP tests, Docker Compose test profile, Python compilation, and JSON config parsing. Mempalace records also showed repeated Docker Desktop socket and localhost access friction from sandboxed sessions.

## Decision
Use `product-layer/scripts/validate.sh` as the standard validation entrypoint for product-layer build, validation-agent, release, and Mempalace documentation loops.

Standard modes:
- `unit`: sandbox-friendly tests, Python compilation, and DPP schema JSON parsing.
- `live`: tests against `TEST_BASE_URL`.
- `docker`: Docker rebuild, host-to-container tests, and Compose service-name tests.
- `all`: `unit` plus `docker`; this is the default pre-documentation path.

## Alternatives considered
- Keep manually typing `TEST_BASE_URL=... python3 -B -m unittest ...` and Docker Compose commands.
- Only run the Compose `test` service and skip host-to-container checks.
- Only run local tests and rely on manual Docker checks later.

## Rationale
One entrypoint removes repeated environment decisions, prevents stale-image false confidence, and makes Docker socket failures explicit. The runner waits for `/health` before host-to-container live tests, which fixes the connection-reset race seen immediately after recreating the service.

## Impact
Product-layer testing now has a single repeatable command for local and Docker validation. The Docker socket limitation is not hidden; if Docker Desktop is unavailable or inaccessible, the script fails with a context/socket diagnostic and the user can still run `scripts/validate.sh unit`.

## Related links
- GitHub issue:
- GitHub PR:
- Related pages:
  - `product-layer/scripts/validate.sh`
  - `product-layer/README.md`
  - `product-layer/docs/architecture.md`
  - `mempalace/product-layer/04_learnings/LEARN-2026-07-02-001-explicit-test-targets.md`
  - `mempalace/product-layer/04_learnings/LRN-2026-07-03-002-dpp-docker-live-tests.md`

## Tags
- product-layer
- data-layer
- governance
- metadata
- access-control
