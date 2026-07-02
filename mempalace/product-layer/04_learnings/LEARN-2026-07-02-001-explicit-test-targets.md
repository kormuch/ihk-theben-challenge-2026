# LEARN-2026-07-02-001 - Explicit test targets avoid sandbox and CI ambiguity

## Situation
Initial HTTP tests tried to bind a local loopback server inside the test process. The sandbox blocked port binding, while Docker/CI needs a way to point the same test suite at a service endpoint.

## Lesson
Live HTTP checks should not hardcode local binds. They should read `TEST_BASE_URL` so the same suite can run against `127.0.0.1`, a Docker service name, or a remote test endpoint.

## Recommendation
Keep local unit tests runnable without network access. Run live HTTP tests only when `TEST_BASE_URL` is set, and use the Docker Compose `test` profile in CI with `TEST_BASE_URL=http://product-layer:8080`.

## Related links
- GitHub issue:
- GitHub PR:
- Incident or decision:
  - `product-layer/tests/test_app.py`
  - `product-layer/docker-compose.yml`
  - `mempalace/product-layer/06_quality-runs/QR-2026-07-02-001-product-layer-local-validation.md`
