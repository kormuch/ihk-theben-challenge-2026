#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."
python3 -B -m unittest discover -s tests -v
python3 -B -m app.app --generate-report --fixtures >/tmp/theben-layer-report.json
find data/reports -name '*.pdf' -size +100c -print -quit | grep -q .
