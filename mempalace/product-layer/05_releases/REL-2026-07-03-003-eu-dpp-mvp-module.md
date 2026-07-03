# REL-2026-07-03-003 - 0.3.0 - EU DPP MVP module

## Released on
2026-07-03 local product-layer Docker environment and source checkout.

## What changed
- Added a curated EU Digital Product Passport record model with JRC three-tier field metadata.
- Added consumer, B2B, and authority DPP views with access-level filtering.
- Added stable public DPP URLs and GS1 Data Matrix payload metadata based on GTIN, batch/lot, and serial number.
- Added public no-login DPP HTML and DPP JSON API surfaces.
- Added lifecycle/version metadata, DPP quality checks, and lightweight audit logging.
- Added DPP validation coverage in local tests, host-to-Docker tests, and Docker Compose test profile.

## Affected areas
- Product layer
- Data layer
- Tests
- Metadata
- Access control

## Verification
Validated by local unit tests, live HTTP tests against the rebuilt Docker container, Docker Compose test profile, Python compilation, JSON schema parsing, and a read-only validation-agent pass against `goal_dpp.md` and `goal.md`.

## Known limitations
Header-based roles remain an MVP/demo authorization model, with optional token gating. Production needs SSO/IAM integration. TLS, reverse proxy, backups, monitoring, and production runtime controls remain open. Data Matrix quality is represented as metadata and payload strings; generated/scanned symbol validation is not implemented yet.

## Related links
- GitHub release/tag:
- GitHub PRs:
- Quality run: `QR-2026-07-03-004-eu-dpp-loop-validation.md`
