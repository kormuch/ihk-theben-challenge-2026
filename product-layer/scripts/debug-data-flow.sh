#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PRODUCT_DIR="$ROOT_DIR/product-layer"
DATA_EXPORT_URL="${DATA_EXPORT_URL:-http://127.0.0.1:8000/api/v1/export/products.json}"
PRODUCT_URL="${PRODUCT_URL:-http://127.0.0.1:8080}"
STORE_PATH="${STORE_PATH:-$PRODUCT_DIR/data/products.json}"
ROLE_HEADER="${ROLE_HEADER:-editor}"
MODE="${1:-}"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

json_summary() {
  python3 - "$1" "$2" <<'PY'
import json
import sys
from pathlib import Path

label = sys.argv[1]
path = Path(sys.argv[2])
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception as exc:
    print(f"{label}: ERROR reading JSON: {exc}")
    raise SystemExit(0)

products = payload.get("products") if isinstance(payload, dict) else None
count = len(products) if isinstance(products, list) else "n/a"
generated = payload.get("generated_at") if isinstance(payload, dict) else None
written_to = payload.get("_written_to") if isinstance(payload, dict) else None
sync_state = payload.get("sync_state") if isinstance(payload, dict) else None
last_sync = sync_state.get("last_sync_at") if isinstance(sync_state, dict) else None
print(f"{label}: products={count} generated_at={generated} last_sync_at={last_sync} written_to={written_to}")
PY
}

echo "== Thebenpaul data flow debug =="
echo "data export:   $DATA_EXPORT_URL"
echo "product api:   $PRODUCT_URL"
echo "shared store:  $STORE_PATH"
echo

echo "== 1. data-layer export endpoint =="
if curl -fsS "$DATA_EXPORT_URL" -o "$tmp_dir/data-export.json"; then
  json_summary "data-layer export" "$tmp_dir/data-export.json"
else
  echo "data-layer export: ERROR. Is data-layer backend running on port 8000?"
fi
echo

echo "== 2. shared product-layer store file =="
if [ -f "$STORE_PATH" ]; then
  ls -l "$STORE_PATH"
  json_summary "shared store" "$STORE_PATH"
else
  echo "shared store: missing"
fi
echo

echo "== 3. product-layer sync contract =="
if curl -fsS "$PRODUCT_URL/api/sync/data-layer" -o "$tmp_dir/product-sync.json"; then
  json_summary "product-layer sync surface" "$tmp_dir/product-sync.json"
  python3 - "$tmp_dir/product-sync.json" <<'PY'
import json
import sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
sync = payload.get("sync", {})
print(f"source_url={sync.get('source_url')}")
print(f"enabled={sync.get('enabled')} mode={sync.get('mode')} permission=product:import")
PY
else
  echo "product-layer sync surface: ERROR. Is product-layer running on port 8080?"
fi
echo

if [ "$MODE" = "--sync" ]; then
  echo "== 4. trigger product-layer pull sync =="
  if curl -fsS -X POST -H "X-Role: $ROLE_HEADER" "$PRODUCT_URL/api/sync/data-layer" -o "$tmp_dir/sync-result.json"; then
    python3 - "$tmp_dir/sync-result.json" <<'PY'
import json
import sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
result = payload.get("result", {})
state = payload.get("sync_state", {})
print(f"synced_at={payload.get('synced_at')}")
print(f"source={payload.get('source')}")
print(f"imported={result.get('imported')} errors={len(result.get('errors') or [])}")
print(f"last_sync_at={state.get('last_sync_at')}")
PY
  else
    echo "sync trigger: ERROR. Check THEBEN_DATA_LAYER_EXPORT_URL, allowed hosts, and X-Role permissions."
  fi
  echo
fi

echo "== 5. product-layer visible products =="
if curl -fsS "$PRODUCT_URL/api/products?limit=1000" -o "$tmp_dir/product-products.json"; then
  json_summary "product-layer api" "$tmp_dir/product-products.json"
else
  echo "product-layer products: ERROR"
fi
