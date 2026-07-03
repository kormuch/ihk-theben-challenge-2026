# OI-2026-07-02-001 - Runtime validation remains open

## Why open
Docker Desktop and the product-layer container are reportedly running, but the active Codex sandbox cannot access the Docker API socket or open outbound localhost sockets to `127.0.0.1:8080`.

The MCP registration part is no longer open. Context7 is callable, my-mempalace is registered, direct my-mempalace MCP smoke tests pass, and the project palace has been initialized and mined.

## Next step
Use the standardized product-layer validation runner from a terminal or CI runner with Docker/network access:

`cd product-layer && scripts/validate.sh all`

For sandbox-only work without Docker access:

`cd product-layer && scripts/validate.sh unit`

Restart Codex/VS Code after MCP config changes if the my-mempalace namespace must appear as a callable tool in the active session.

## Owner
Platform/tooling owner.

## Blocking factors
Sandbox socket/network permission for direct live Docker validation. The product-layer workaround is standardized through `scripts/validate.sh`, which fails with an explicit Docker context/socket diagnostic when Docker is unavailable and otherwise runs the complete Docker validation path.

## Related links
- GitHub issue:
- GitHub PR:
- Related notes:
  - `mempalace/product-layer/03_incidents/INC-2026-07-02-001-docker-and-mcp-visibility.md`
  - `mempalace/product-layer/06_quality-runs/QR-2026-07-02-001-product-layer-local-validation.md`
  - `mempalace/product-layer/06_quality-runs/QR-2026-07-02-002-live-container-endpoint-attempt.md`
  - `mempalace/product-layer/06_quality-runs/QR-2026-07-03-001-mcp-server-repair.md`
  - `mempalace/product-layer/01_decisions/ADR-2026-07-03-005-standard-validation-runner.md`
  - `mempalace/product-layer/06_quality-runs/QR-2026-07-03-005-standard-validation-runner.md`
