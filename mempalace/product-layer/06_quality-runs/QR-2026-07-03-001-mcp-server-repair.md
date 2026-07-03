# QR-2026-07-03-001 - MCP server repair and Mempalace mining

## Purpose
Validate that Context7 and my-mempalace are configured for the Thebenpaul loop, and that Mempalace can document architecture decisions, learnings, incidents, release notes, and quality runs across `data-layer` and `product-layer`.

## Scope
Checked:
- Codex MCP registry entries
- Workspace MCP JSON config at `/Users/Shared/code/paul/.vscode/mcp.json`
- Context7 library resolution
- my-mempalace stdio startup and tool discovery
- Project Mempalace initialization and mining for `ihk-theben-challenge-2026`
- Mempalace search over product-layer and data-layer notes

## Results
- Passed: `codex mcp list` shows `io-github-upstash-context7` and `my-mempalace` enabled.
- Passed: `.vscode/mcp.json` validates with `python3 -m json.tool`.
- Passed: Context7 resolves `Docker Compose` and returns `/docker/compose`.
- Passed: my-mempalace direct stdio smoke test returns server `mempalace 3.4.1` and exposes MCP tools.
- Passed: `mempalace_status` reports indexed drawers across `product_layer`, `data_layer`, `mempalace`, and `general`.
- Failed: none for MCP registration.
- Skipped: active-session dynamic my-mempalace tool namespace; a Codex/VS Code reload is required for newly registered MCP tools to surface in the current tool list.

## Observations
The user-provided JSON structure is valid for the workspace config. my-mempalace required three operational additions to work reliably in this repository:

- `--palace /Users/Shared/code/paul/ihk-theben-challenge-2026/mempalace`
- `HOME=/Users/Shared/code/paul/ihk-theben-challenge-2026/mempalace`
- `UV_CACHE_DIR=/private/tmp/uv-cache`

The previous my-mempalace Codex entry had an incorrect command/argument shape and stale working path. After repair, direct line-delimited JSON-RPC smoke tests succeeded, and Mempalace search returned product-layer documentation hits.

## Action items
- Restart the active Codex/VS Code session before expecting a new `my-mempalace` tool namespace to appear.
- Keep generated Mempalace vector/cache artifacts out of Git; keep Markdown notes and templates as source.
- Continue documenting validated loops using the `99_shared/*_template` structures.

## Related links
- GitHub workflow:
- Logs:
  - `codex mcp list`
  - `mempalace/product-layer/03_incidents/INC-2026-07-02-001-docker-and-mcp-visibility.md`
  - `mempalace/product-layer/07_open-items/OI-2026-07-02-001-runtime-validation-and-mcp.md`
- Release:
  - `mempalace/product-layer/05_releases/REL-2026-07-02-001-product-layer-mvp.md`
