# INC-2026-07-02-001 - Docker socket and MCP tools not reachable from Codex sandbox

## Summary
Docker Desktop is running and the `desktop-linux` context points at the current Docker Desktop socket, but the Codex sandbox cannot connect to the socket. Context7 and my-mempalace MCP servers were also not exposed as callable tools or resources in this session.

## Environment
- Repo: `ihk-theben-challenge-2026`
- Branch: `main`
- Runtime: Codex workspace sandbox
- Docker/VM: Docker Desktop for Mac, context `desktop-linux`, socket `unix:///Users/christianspindler/.docker/run/docker.sock`
- Date: 2026-07-02

## Symptoms
`docker version` and `docker --context desktop-linux version` reported permission denied while connecting to the Docker API socket. `tool_search` returned no callable Context7 or my-mempalace tools, and MCP resource listing only exposed `codex_apps`.

After the user provided a running `docker run ... -p 8080:8080 ... thebenpaul/product-layer:local` container command, live HTTP validation against `http://127.0.0.1:8080` still failed from the Codex sandbox with `PermissionError: [Errno 1] Operation not permitted` during socket connect.

## Root cause
The Docker socket is outside the sandbox's allowed execution boundary, and approval escalation is disabled. The running Context7 and my-mempalace servers are not registered in the active Codex tool surface.

## Fix
No code fix was possible inside this sandbox. Product-layer tests were made environment-driven and Docker Compose config was validated statically. Mempalace documentation was written directly to the repo's `mempalace/` folder using the shared templates.

## Preventive action
Expose the Docker socket to the Codex sandbox or run Docker validation outside the sandbox. Register Context7 and my-mempalace as Codex-callable MCP servers before requiring tool-backed documentation.

## Verification
Validated:
- `docker context ls` found `desktop-linux`.
- `docker compose --profile test config` rendered the test profile.
- `python3 -B -m unittest discover -s tests -v` passed locally with live HTTP tests skipped unless `TEST_BASE_URL` is set.
- `TEST_BASE_URL=http://127.0.0.1:8080 python3 -B -m unittest discover -s tests -v` attempted live HTTP checks but failed at sandbox socket connect.

## Related links
- GitHub issue:
- GitHub PR:
- Logs:
  - Docker socket: `unix:///Users/christianspindler/.docker/run/docker.sock`
- Tests:
  - `python3 -B -m unittest discover -s tests -v`
  - `mempalace/product-layer/06_quality-runs/QR-2026-07-02-002-live-container-endpoint-attempt.md`

## Tags
- incident
- test
- sandbox
- docker
- quality
