#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
out_dir="${TMPDIR:-/tmp}/agenttrace-demo-$$"
mkdir -p "$out_dir"
python3 -m agenttrace validate examples/trace.jsonl
python3 -m agenttrace analyze examples/trace.jsonl --json "$out_dir/analysis.json" --junit "$out_dir/analysis.xml" --markdown "$out_dir/analysis.md" --fail-on-error --max-loop-repeat 3 --max-p95-ms 500 --max-cost-usd 0.01 --max-steps 10
python3 -m agenttrace report examples/trace.jsonl --out "$out_dir/report.html" --fail-on-error --max-loop-repeat 3 --max-p95-ms 500 --max-cost-usd 0.01 --max-steps 10
python3 -m agenttrace compare examples/trace.jsonl examples/trace_candidate.jsonl --json "$out_dir/compare.json" --max-new-errors 0 --max-p95-increase-ms 100 --max-cost-increase-pct 50
python3 - <<PY
import xml.etree.ElementTree as ET
root = ET.parse("$out_dir/analysis.xml").getroot()
assert root.attrib["tests"] == "2"
assert root.attrib["failures"] == "0"
assert len(root.findall("testcase")) == 2
summary = open("$out_dir/analysis.md", encoding="utf-8").read()
assert summary.startswith("# AgentTrace analysis\n")
assert "**Status:** PASS" in summary
assert "## Validation and gates" in summary
PY
printf 'demo artifacts: %s\n' "$out_dir"
