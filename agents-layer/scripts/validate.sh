#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"

python3 -m json.tool config/rule_catalog.json >/dev/null
python3 -m json.tool config/evidence_model.json >/dev/null
python3 -m json.tool config/access_control.json >/dev/null
python3 -m json.tool config/runtime.json >/dev/null
PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-/private/tmp/thebenpaul-agents-pycache}" \
PYTHONPATH="$ROOT" \
python3 -B -m unittest discover -s tests -v

