# INC-2026-07-02-001 - Docker socket and MCP tools not reachable from Codex sandbox

## Summary
Docker Desktop is running and the `desktop-linux` context points at the current Docker Desktop socket, but the Codex sandbox cannot connect to the socket. Context7 and my-mempalace MCP servers were initially not exposed as callable tools or resources in this session; Context7 and my-mempalace registration were repaired on 2026-07-03.

## Environment
- Repo: `ihk-theben-challenge-2026`
- Branch: `main`
- Runtime: Codex workspace sandbox
- Docker/VM: Docker Desktop for Mac, context `desktop-linux`, socket `unix:///Users/christianspindler/.docker/run/docker.sock`
- Date: opened 2026-07-02, MCP repair verified 2026-07-03

## Symptoms
`docker version` and `docker --context desktop-linux version` reported permission denied while connecting to the Docker API socket. `tool_search` returned no callable Context7 or my-mempalace tools, and MCP resource listing only exposed `codex_apps`.

After the user provided a running `docker run ... -p 8080:8080 ... thebenpaul/product-layer:local` container command, live HTTP validation against `http://127.0.0.1:8080` still failed from the Codex sandbox with `PermissionError: [Errno 1] Operation not permitted` during socket connect.

The existing my-mempalace Codex registration used a wrong command shape and stale working path. Direct smoke testing also showed that the server accepts line-delimited JSON-RPC messages.

## Root cause
The Docker socket and localhost networking are outside the sandbox's allowed execution boundary for this session. The MCP issue was configuration drift: Context7 was available through the Codex MCP registry, while my-mempalace needed the correct `uv --directory /Users/Shared/code/mempalace run mempalace-mcp --palace /Users/Shared/code/paul/ihk-theben-challenge-2026/mempalace` command and project-local environment paths.

## Fix
Product-layer tests were made environment-driven and Docker Compose config was validated statically. Mempalace documentation was written directly to the repo's `mempalace/` folder using the shared templates.

For MCP, the broken my-mempalace registration was removed and recreated as `my-mempalace`. Workspace MCP config was added at `/Users/Shared/code/paul/.vscode/mcp.json` using the requested server JSON plus the required `--palace`, `HOME`, and `UV_CACHE_DIR` settings. The project palace was initialized and mined.

## Preventive action
Expose the Docker socket to the Codex sandbox or run Docker validation outside the sandbox. Keep the workspace `.vscode/mcp.json` and Codex MCP registry aligned. Restart the Codex/VS Code session after MCP changes so newly registered tools appear in the active tool surface.

## Verification
Validated:
- `docker context ls` found `desktop-linux`.
- `docker compose --profile test config` rendered the test profile.
- `python3 -B -m unittest discover -s tests -v` passed locally with live HTTP tests skipped unless `TEST_BASE_URL` is set.
- `TEST_BASE_URL=http://127.0.0.1:8080 python3 -B -m unittest discover -s tests -v` attempted live HTTP checks but failed at sandbox socket connect.
- `codex mcp list` shows `io-github-upstash-context7` and `my-mempalace` enabled.
- Context7 resolved `Docker Compose` to `/docker/compose`.
- my-mempalace direct stdio smoke test returned server `mempalace 3.4.1`, exposed MCP tools, and `mempalace_status` reported indexed drawers across `product_layer`, `data_layer`, `mempalace`, and `general`.

## Related links
- GitHub issue:
- GitHub PR:
- Logs:
  - Docker socket: `unix:///Users/christianspindler/.docker/run/docker.sock`
- Tests:
  - `python3 -B -m unittest discover -s tests -v`
  - `mempalace/product-layer/06_quality-runs/QR-2026-07-02-002-live-container-endpoint-attempt.md`
  - `mempalace/product-layer/06_quality-runs/QR-2026-07-03-001-mcp-server-repair.md`

## Tags
- incident
- test
- sandbox
- docker
- quality
