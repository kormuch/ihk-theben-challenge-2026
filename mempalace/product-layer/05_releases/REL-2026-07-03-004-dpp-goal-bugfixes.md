# REL-2026-07-03-004 - 0.3.1 - DPP goal bugfixes

## Released on
2026-07-03 local product-layer source and Docker validation environment.

## What changed
- Public DPP scan resolution now returns consumer DPP records without row-level filtering.
- Public DPP JSON-LD is emitted as parseable script JSON.
- Read, write, update, scan, and export paths now write audit events with actor, role, action, channel, time, and scope.
- DPP records can be updated through `/api/dpp/{id}` with version history and change rationale.
- Public DPP URLs now use a stable HTTPS base URL from `THEBEN_PUBLIC_BASE_URL` or `config/runtime.json`.
- Security and cache headers are explicit for API and public DPP surfaces.

## Affected areas
- Product layer
- Data layer
- Tests
- Metadata
- Access control

## Verification
Verified by `scripts/validate.sh unit`, `scripts/validate.sh all`, Python compilation, JSON config validation, and focused verify-agent review. Full standard validation rebuilt the product-layer Docker image, checked host-to-container live HTTP behavior, and ran the Docker Compose test profile.

## Known limitations
The product-layer remains an MVP over JSON-file persistence with target contracts for Iceberg, Trino, OpenMetadata, and platform IAM. Production TLS termination, SSO/IAM, Data Matrix symbol verification, multilingual DPP rendering, Ollama LAN runtime checks, and data-layer Iceberg/OpenMetadata implementation remain open hardening items.

## Related links
- GitHub release/tag:
- GitHub PRs:
- Quality run: `QR-2026-07-03-006-dpp-goal-bugfix-validation.md`
