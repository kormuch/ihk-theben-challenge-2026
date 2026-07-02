# QR-2026-07-02-002 - Live container endpoint validation attempt

## Purpose
Validate the running product-layer Docker container through the host-mapped endpoint `http://127.0.0.1:8080` using the same unittest suite with `TEST_BASE_URL`.

## Scope
Checked:
- Local unit-only test suite
- Live HTTP test suite against `TEST_BASE_URL=http://127.0.0.1:8080`
- Direct `/health`, `/api/openapi.json`, and `/api/products?limit=1` endpoint probe
- User-provided Docker runtime command for the running `thebenpaul/product-layer:local` container

## Results
- Passed: `python3 -B -m unittest discover -s tests -v`, 12 tests run, 9 passed, 3 live HTTP tests skipped.
- Failed: `TEST_BASE_URL=http://127.0.0.1:8080 python3 -B -m unittest discover -s tests -v`, 3 live HTTP tests errored.
- Skipped: none in the live run; the live tests attempted to connect and were blocked by the sandbox.

## Observations
The Docker container is reported as running with host port `8080:8080`, but the Codex sandbox cannot open outbound localhost sockets. The failure is `PermissionError: [Errno 1] Operation not permitted` from Python socket connect, not an HTTP application failure response.

User-provided runtime shape:

```bash
docker run --hostname=a12c56dfb2d2 --env=PORT=8080 --env=THEBEN_DEFAULT_ROLE=viewer --env=THEBEN_DATA_DIR=/app/data --env=HOST=0.0.0.0 --volume=/Users/Shared/code/paul/ihk-theben-challenge-2026/product-layer/data:/app/data:rw --volume=/Users/Shared/code/paul/ihk-theben-challenge-2026/product-layer/config:/app/config:ro --network=product-layer_default --workdir=/app -p 8080:8080 --restart=unless-stopped -d thebenpaul/product-layer:local
```

## Action items
- Run the live validation command from a non-sandboxed terminal on the host:
  `TEST_BASE_URL=http://127.0.0.1:8080 python3 -B -m unittest discover -s tests -v`
- Or run the Docker Compose test profile from a terminal with Docker socket access:
  `docker compose --profile test up --build --abort-on-container-exit --exit-code-from test test`
- Register Context7 and my-mempalace MCP servers in the active Codex tool surface if they must be used directly by Codex.

## Related links
- GitHub workflow:
- Logs:
  - `mempalace/product-layer/03_incidents/INC-2026-07-02-001-docker-and-mcp-visibility.md`
- Release:
  - `mempalace/product-layer/05_releases/REL-2026-07-02-001-product-layer-mvp.md`
