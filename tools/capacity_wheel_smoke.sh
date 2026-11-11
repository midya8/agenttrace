#!/bin/sh
set -eu
ROOT=$(pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
python -m venv "$TMP/env"
"$TMP/env/bin/pip" -q wheel --no-deps --wheel-dir "$TMP/wheels" "$ROOT"
"$TMP/env/bin/pip" -q install --no-deps "$TMP"/wheels/*.whl
(cd "$TMP" && PYTHONPATH= "$TMP/env/bin/python" -I "$ROOT/tools/verify_capacity_installed.py" "$ROOT")
