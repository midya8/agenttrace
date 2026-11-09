#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)";trap 'rm -rf "$tmp"' EXIT
python -m pip wheel --no-deps --wheel-dir "$tmp/dist" "$root" > "$tmp/build.log"
python -m venv "$tmp/env"
"$tmp/env/bin/python" -m pip install --no-deps "$tmp"/dist/*.whl > "$tmp/install.log"
cd "$tmp"
"$tmp/env/bin/python" -I "$root/tools/verify_installed.py" "$root"
"$tmp/env/bin/agenttrace" audit --spec "$root/examples/audit.json" --json audit.json
"$tmp/env/bin/agenttrace" validate "$root/examples/trace.jsonl"
"$tmp/env/bin/agenttrace" analyze "$root/examples/trace.jsonl" --json analysis.json --junit analysis.xml --markdown analysis.md --sarif analysis.sarif --fail-on-error
"$tmp/env/bin/agenttrace" report "$root/examples/trace.jsonl" --out report.html
"$tmp/env/bin/agenttrace" compare "$root/examples/trace.jsonl" "$root/examples/trace_candidate.jsonl" --json compare.json
"$tmp/env/bin/python" -I - "$root" <<'PY'
import json,sys,pathlib,xml.etree.ElementTree as ET
from agenttrace.audit import audit_trace
root=pathlib.Path(sys.argv[1]);assert json.load(open('audit.json'))==audit_trace(json.load(open(root/'examples/audit.json')))
assert json.load(open('analysis.json'))['ok'];assert json.load(open('compare.json'))['ok'];assert json.load(open('analysis.sarif'))['version']=='2.1.0';ET.parse('analysis.xml');assert pathlib.Path('analysis.md').read_text().startswith('# AgentTrace');assert '<html' in pathlib.Path('report.html').read_text()
print('Installed audit/validate/analyze/report/compare CLI and JSON/HTML/JUnit/Markdown/SARIF pass')
PY
