# OI-2026-07-02-001 - Runtime validation remains open

## Why open
Docker Desktop and the product-layer container are reportedly running, but the active Codex sandbox cannot access the Docker API socket or open outbound localhost sockets to `127.0.0.1:8080`.

The MCP registration part is no longer open. Context7 is callable, my-mempalace is registered, direct my-mempalace MCP smoke tests pass, and the project palace has been initialized and mined.

## Next step
Run live validation from a non-sandboxed terminal or CI runner with Docker/network access:

`TEST_BASE_URL=http://127.0.0.1:8080 python3 -B -m unittest discover -s tests -v`

Restart Codex/VS Code after MCP config changes if the my-mempalace namespace must appear as a callable tool in the active session.

## Owner
Platform/tooling owner.

## Blocking factors
Sandbox socket/network permission for live Docker validation.

## Related links
- GitHub issue:
- GitHub PR:
- Related notes:
  - `mempalace/product-layer/03_incidents/INC-2026-07-02-001-docker-and-mcp-visibility.md`
  - `mempalace/product-layer/06_quality-runs/QR-2026-07-02-001-product-layer-local-validation.md`
  - `mempalace/product-layer/06_quality-runs/QR-2026-07-02-002-live-container-endpoint-attempt.md`
  - `mempalace/product-layer/06_quality-runs/QR-2026-07-03-001-mcp-server-repair.md`
