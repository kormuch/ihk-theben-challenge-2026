# QR-2026-07-03-005 - Standard validation runner verification

## Purpose
Validate that `product-layer/scripts/validate.sh` standardizes the product-layer test environment and removes repeated manual Docker/live-test command changes.

## Scope
Validated the new runner, README test instructions, architecture documentation, Docker rebuild behavior, host-to-container live HTTP tests, Docker Compose service-name tests, Python compilation, and DPP schema JSON parsing.

## Results
- Passed: `sh -n scripts/validate.sh`.
- Passed: `scripts/validate.sh unit`, 25 tests OK with 4 live HTTP tests skipped by default, plus Python compilation and DPP schema JSON parsing.
- Passed after health-wait fix: `scripts/validate.sh all`, including unit checks, Docker image rebuild, host-to-container live tests, and Compose `test` profile.
- Failed initially: `scripts/validate.sh all` started live host tests before the recreated container was ready, causing `ConnectionResetError`.
- Skipped: none after the health-wait fix, except the intentional live HTTP skips in `unit` mode.

## Observations
The important failure was a timing race, not a product-layer route bug. Adding a `/health` wait before host-to-container tests made the runner stable and kept Docker runtime validation inside the standard path.

## Action items
- Use `scripts/validate.sh all` before documenting future product-layer loops as complete.
- Use `scripts/validate.sh unit` only when Docker access is intentionally unavailable.
- Keep Docker socket permission failures explicit; they are environment/tooling issues, not product-layer test failures.

## Related links
- GitHub workflow:
- Logs:
- Release:
