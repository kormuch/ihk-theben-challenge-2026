#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
MODE="${1:-all}"
DEFAULT_TEST_BASE_URL="http://127.0.0.1:${PRODUCT_LAYER_PORT:-8080}"

cd "$ROOT_DIR"

usage() {
  cat <<'EOF'
Usage: scripts/validate.sh [unit|live|docker|all]

Modes:
  unit    Run sandbox-friendly unit/parser/model tests. Live HTTP tests are skipped.
  live    Run the suite against TEST_BASE_URL, defaulting to http://127.0.0.1:8080.
  docker  Rebuild product-layer and run the Compose test profile against product-layer:8080.
  all     Run unit, then docker. This is the standard pre-documentation validation path.

Environment:
  TEST_BASE_URL       Endpoint for live mode. Default: http://127.0.0.1:${PRODUCT_LAYER_PORT:-8080}
  PRODUCT_LAYER_PORT  Host port used by docker compose. Default: 8080
EOF
}

run_unit() {
  python3 -B -m unittest discover -s tests -v
  PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-/private/tmp/thebenpaul-pycache}" python3 -m py_compile app/app.py tests/test_app.py
  python3 -m json.tool config/dpp_schema.json >/dev/null
}

require_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker CLI not found. Install/start Docker Desktop or run unit validation only." >&2
    exit 2
  fi
  if ! docker info >/dev/null 2>&1; then
    echo "Docker is not reachable from this shell." >&2
    echo "Start Docker Desktop and run this from a terminal/session with Docker socket access." >&2
    echo "Current Docker context, if available:" >&2
    docker context show 2>/dev/null >&2 || true
    docker context inspect "$(docker context show 2>/dev/null)" --format '{{.Endpoints.docker.Host}}' 2>/dev/null >&2 || true
    exit 2
  fi
}

run_live() {
  TEST_BASE_URL="${TEST_BASE_URL:-$DEFAULT_TEST_BASE_URL}" python3 -B -m unittest discover -s tests -v
}

wait_for_live_endpoint() {
  url="${1%/}/health"
  limit="${2:-60}"
  count=0
  while [ "$count" -lt "$limit" ]; do
    if HEALTHCHECK_URL="$url" python3 -c 'import os; from urllib.request import urlopen; urlopen(os.environ["HEALTHCHECK_URL"], timeout=2).read()' >/dev/null 2>&1; then
      return 0
    fi
    count=$((count + 1))
    sleep 1
  done
  echo "Timed out waiting for $url" >&2
  docker compose ps product-layer >&2 || true
  docker compose logs --tail=80 product-layer >&2 || true
  exit 1
}

run_docker() {
  require_docker
  docker compose up --build -d product-layer
  TEST_BASE_URL="${TEST_BASE_URL:-$DEFAULT_TEST_BASE_URL}"
  wait_for_live_endpoint "$TEST_BASE_URL" 60
  TEST_BASE_URL="$TEST_BASE_URL" python3 -B -m unittest discover -s tests -v
  docker compose --profile test run --rm test
}

case "$MODE" in
  unit)
    run_unit
    ;;
  live)
    run_live
    ;;
  docker)
    run_docker
    ;;
  all)
    run_unit
    run_docker
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
