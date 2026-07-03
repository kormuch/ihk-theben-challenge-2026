# QR-2026-07-03-004 - EU DPP build/verify loop validation

## Purpose
Validate the product-layer DPP MVP against `Thebenpaul/goal_dpp.md` and `Thebenpaul/goal.md` after the build-agent implementation loop and verification-agent feedback.

## Scope
Validated product-layer code, DPP schema/config, public/API routes, role-filtered DPP records, Data Matrix identity payloads, lifecycle/version/audit surfaces, data-layer interface metadata, local tests, host-to-Docker HTTP tests, and Docker Compose test profile.

## Results
- Passed: `python3 -B -m unittest discover -s tests -v` with 25 tests OK and 4 live HTTP tests skipped by default.
- Passed: `TEST_BASE_URL=http://127.0.0.1:8080 python3 -B -m unittest discover -s tests -v` with 25 tests OK.
- Passed: `docker compose --profile test run --rm test` with 25 tests OK against `http://product-layer:8080`.
- Passed: `PYTHONPYCACHEPREFIX=/private/tmp/thebenpaul-pycache python3 -m py_compile app/app.py tests/test_app.py`.
- Passed: `python3 -m json.tool config/dpp_schema.json`.
- Failed: none blocking after consolidation.
- Skipped: live HTTP tests are skipped in the default local test command unless `TEST_BASE_URL` is set.

## Observations
The first validation pass found duplicate DPP model functions, shadowed DPP routes, stale public route behavior, synthetic audit/version behavior, and a stale Docker image. The final implementation uses one canonical DPP record shape, records DPP API/public reads, serves public `/dpp/{id}` from raw product data for no-login scan access, and has live tests that cover DPP JSON and HTML endpoints.

## Action items
- Keep production SSO/IAM as a tracked hardening item; current token-gated role headers remain MVP infrastructure.
- Add real TLS/reverse proxy, backup, and monitoring before production deployment.
- Add generated/scanned Data Matrix symbol validation when moving beyond metadata-level DPP carrier proof.

## Related links
- GitHub workflow:
- Logs:
- Release: `REL-2026-07-03-003-eu-dpp-mvp-module.md`
