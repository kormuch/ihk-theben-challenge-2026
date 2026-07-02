# OI-2026-07-02-001 - Runtime validation and MCP-backed documentation remain open

## Why open
Docker Desktop, the product-layer container, and the MCP servers are reportedly running, but the active Codex sandbox cannot access the Docker API socket, cannot open outbound localhost sockets to `127.0.0.1:8080`, and does not expose callable Context7 or my-mempalace tools.

## Next step
Run live validation from a non-sandboxed terminal or CI runner with Docker/network access and expose Context7/my-mempalace MCP servers to Codex tool discovery.

## Owner
Platform/tooling owner.

## Blocking factors
Sandbox socket/network permission and missing Codex MCP tool registration.

## Related links
- GitHub issue:
- GitHub PR:
- Related notes:
  - `mempalace/product-layer/03_incidents/INC-2026-07-02-001-docker-and-mcp-visibility.md`
  - `mempalace/product-layer/06_quality-runs/QR-2026-07-02-001-product-layer-local-validation.md`
  - `mempalace/product-layer/06_quality-runs/QR-2026-07-02-002-live-container-endpoint-attempt.md`
