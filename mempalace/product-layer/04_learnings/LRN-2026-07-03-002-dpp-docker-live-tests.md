# LRN-2026-07-03-002 - DPP Docker live tests caught stale runtime code

## Situation
The source-level test suite passed after the DPP implementation was consolidated, but the running Docker container still returned `404` for `/api/dpp/thb-tim-0001`. The container image had not yet been rebuilt after source changes.

## Lesson
For this project, source-level tests are not enough. DPP endpoint tests must also run against the actual Docker image and Compose network because the product-layer image copies source at build time while only `data` and `config` are mounted at runtime.

## Recommendation
Keep the DPP live HTTP test in `tests/test_app.py` and run the Docker Compose test profile before documenting a loop as complete. Use `TEST_BASE_URL` for local host checks and the Compose `test` profile for service-name checks.

## Related links
- GitHub issue:
- GitHub PR:
- Incident or decision: `ADR-2026-07-03-004-eu-dpp-mvp-module.md`
