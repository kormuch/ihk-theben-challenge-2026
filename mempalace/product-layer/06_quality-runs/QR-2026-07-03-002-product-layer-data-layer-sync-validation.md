# QR-2026-07-03-002 - Product-layer data-layer sync validation

## Purpose
Validate the product-layer implementation against `Thebenpaul/goal.md`: lakehouse modules, data product metadata, data-layer interface use, access controls, Docker-first runtime configuration, and testability.

## Scope
Checked:
- Product-layer stdlib API and UI.
- Data-layer export contract `/api/v1/export/products.json`.
- Config-as-code in `product-layer/config/runtime.json`.
- Docker Compose rendering for product-layer.
- Unit tests for catalog, lineage, data-layer sync, RBAC/ABAC behavior, masking, CSV import/export, validation, and static path safety.
- Auto-reload behavior for the shared `data/products.json` bridge.
- Debug script syntax for `product-layer/scripts/debug-data-flow.sh`.
- Validation-agent findings and follow-up fixes.

## Results
- Passed: `PYTHONPYCACHEPREFIX=/private/tmp/thebenpaul-pycache python3 -B -m unittest tests/test_app.py -v`, 32 tests run, 28 passed, 4 live HTTP tests skipped because `TEST_BASE_URL` is unset.
- Passed: `docker compose --profile test config`.
- Passed: `PYTHONPYCACHEPREFIX=/private/tmp/thebenpaul-pycache python3 -m py_compile app/app.py tests/test_app.py`.
- Passed: `bash -n scripts/debug-data-flow.sh`.
- Passed: `test_store_auto_reloads_when_shared_file_changes`.
- Passed: validation agent second pass reported no blocking findings.
- Failed: live `TEST_BASE_URL=http://127.0.0.1:8080 python3 -B -m unittest discover -s tests -v` cannot run inside the Codex sandbox because socket connect returns `PermissionError: [Errno 1] Operation not permitted`.
- Skipped: Docker runtime execution and live localhost HTTP validation inside the sandbox.

## Observations
The first validation pass found configuration drift, duplicate Compose environment keys, an arbitrary sync URL risk, and overlapping sync implementations. These were fixed by consolidating sync through `sync_from_data_layer`, making the source configuration-only, adding allowed-host validation, aligning timeout environment variables, and removing duplicate Compose keys.

The immediate-visibility issue is caused by process memory, not by the shared file write. Data-layer can update `product-layer/data/products.json` immediately, while product-layer previously kept the startup copy in memory. Product-layer now reloads the file on read when the mtime changes. The explicit sync endpoint remains useful for auditing and for environments where the shared file bridge is not mounted.

Context7 library resolution was available earlier in the loop, but the documentation fetch returned an API-key error. The implementation did not depend on external Context7 output.

## Action items
- Run the live HTTP suite from a host terminal or CI runner with network access.
- If data-layer and product-layer run in separate Compose projects on Docker Desktop for Mac, keep `THEBEN_DATA_LAYER_EXPORT_URL=http://host.docker.internal:8000/api/v1/export/products.json`.
- If both services are joined to one Compose network, override the URL and `THEBEN_DATA_LAYER_ALLOWED_HOSTS` to the selected service name.

## Related links
- GitHub workflow:
- Logs:
  - `product-layer/tests/test_app.py`
  - `product-layer/docker-compose.yml`
  - `product-layer/config/runtime.json`
- Release:
  - `product-layer/05_releases/REL-2026-07-03-002-product-layer-data-layer-sync.md`
