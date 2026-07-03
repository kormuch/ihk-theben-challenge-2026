# QR-2026-07-03-006 - DPP goal bugfix validation

## Purpose
Validate the product-layer against `Thebenpaul/goal.md` and `Thebenpaul/goal_dpp.md` after reviewing open TODOs, bugs, and errors from the build-agent and verify-agent loop.

## Scope
Validated public DPP scan behavior, parseable public JSON-LD, read/write/export audit coverage, actor identity in audit events, explicit DPP update/version APIs, stable HTTPS public DPP URL generation, security/cache headers, runtime configuration, and Docker-backed validation.

## Results
- Passed: priority review found no P0 issues.
- Passed: build-agent fixed P1 DPP alignment issues in product-layer.
- Passed: verify-agent confirmed no remaining P1/P2 product-layer findings in the focused scope.
- Passed: `scripts/validate.sh unit`, 31 tests OK with 4 live HTTP tests intentionally skipped.
- Passed: `scripts/validate.sh all`, including unit checks, image rebuild, host-to-container live HTTP tests, and Docker Compose service-name tests.
- Failed: initial review found P1 gaps for public scan row filtering, JSON-LD escaping, partial audit coverage, synthetic DPP versioning, and unstable HTTP public DPP URLs. These were fixed in this loop.
- Skipped: none in full `scripts/validate.sh all`; live tests are only skipped in `unit` mode by design.

## Observations
The strongest runtime issue was stable DPP URL generation. Public DPP URLs now come from `THEBEN_PUBLIC_BASE_URL` or `config/runtime.json` `service.public_base_url`, not from arbitrary caller host headers. Audit events now include an actor and cover product reads, validation reads, summaries, exports, DPP reads, public scans, public HTML reads, writes, imports, sync, and DPP updates.

## Action items
- Keep `scripts/validate.sh all` as the standard pre-documentation validation command.
- Track remaining non-blocking architecture gaps separately: production IAM/SSO, TLS/reverse proxy operation, real Data Matrix symbol verification, multilingual DPP rendering, Ollama LAN reachability checks, and data-layer Iceberg/OpenMetadata implementation.

## Related links
- GitHub workflow:
- Logs:
- Release: `REL-2026-07-03-004-dpp-goal-bugfixes.md`
