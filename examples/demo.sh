#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
out_dir="${TMPDIR:-/tmp}/agenttrace-demo-$$"
mkdir -p "$out_dir"
python3 -m agenttrace validate examples/trace.jsonl
python3 -m agenttrace analyze examples/trace.jsonl --json "$out_dir/analysis.json" --fail-on-error --max-loop-repeat 3 --max-p95-ms 500 --max-cost-usd 0.01 --max-steps 10
python3 -m agenttrace report examples/trace.jsonl --out "$out_dir/report.html" --fail-on-error --max-loop-repeat 3 --max-p95-ms 500 --max-cost-usd 0.01 --max-steps 10
printf 'demo artifacts: %s\n' "$out_dir"
