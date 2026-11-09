# AgentTrace

Local-first validation, analysis and reporting for AI agent traces, now with complete graph/timing evidence.

[Open the timing inspector](https://midya8.github.io/agenttrace/) · [Definitions and prior work](EVIDENCE.md) · [Original README](docs/original-readme.md)

## A parent is not a stopwatch

Summing overlapping event durations is not elapsed time. A parent link is not proof of a finish-to-start dependency. AgentTrace now exposes every interval transition, active set, coverage segment, parent path, parent/child time relation and p95 interpolation term in an independently recomputed browser.

The original standard-library JSONL validator/analyzer, loop/error/token/cost summaries, configurable gates and standalone HTML/JUnit/Markdown/SARIF reports remain. The included five-step baseline and candidate are fixed synthetic fixtures, not model/API measurements.

## Run

```bash
python -m agenttrace validate examples/trace.jsonl
python -m agenttrace analyze examples/trace.jsonl --json analysis.json \
  --junit analysis.xml --markdown analysis.md --sarif analysis.sarif \
  --fail-on-error --max-loop-repeat 3 --max-p95-ms 500 --max-cost-usd .01 --max-steps 10
python -m agenttrace report examples/trace.jsonl --out report.html
python -m agenttrace compare examples/trace.jsonl examples/trace_candidate.jsonl \
  --json comparison.json --max-new-errors 0 --max-p95-increase-ms 100
python -m agenttrace audit --spec examples/audit.json --json audit.json
bash examples/demo.sh
```

Events require run_id/step/kind/name. Kinds: llm/tool/action/observation/error; statuses: ok/failed/cancelled/timeout. Optional parent, ISO started_at, nonnegative duration_ms/cost_usd, integer tokens_input/tokens_output, arbitrary input/output payloads. Parent references may arrive out of order, but must resolve inside the same run and form an acyclic forest. A root has parent=null or omitted. Native parser issues retain source line numbers; duplicate step records remain visible but invalidate graph analysis. Duplicate JSON keys and nonfinite JSON tokens are rejected; known numeric fields must be finite. This is structural validation, not provenance/authenticity or a general arbitrary-payload schema.

Mixed present/missing timestamps no longer crash sorting. Iterative graph depth handles deep chains without recursion. Parser/graph issues now make analysis JSON ok=false and comparison gates fail, matching the CLI's existing nonzero behavior on invalid traces. Invalid numeric gate options are rejected. A zero-baseline percentage change is undefined/null rather than nonstandard Infinity JSON; positive growth still fails a configured percentage limit. The default loop gate and error/latency/cost/size choices remain configurable. Loop signatures are repeated normalized kind/name/input, not proof of an actual control-flow cycle.

## Inspect every witness

Edit the entire events list and inspect each run:

- **Time:** step-duration sum versus first-to-last recorded span, union coverage, uncovered span, overlap excess and peak recorded spans. Every half-open endpoint transition and constant-active segment is retained. Ends are removed before starts; zero-duration events are points, never active intervals. Unknown timestamps remain unknown and coverage is explicitly partial.
- **Structure:** iterative topological order, roots, every root-to-step path and depth. Path-duration sums can double-count nested spans and are never called a critical path. Parent/child time relations are exposed, not silently repaired or automatically classified as errors.
- **Tail:** every sorted duration and the original linear p95 rank, neighbors, weight and result. This is a convention, not nearest rank, uncertainty or predicted runtime.

The shared per-run timeline uses relative milliseconds on one fixed axis. Every timed mark and untimed row remains visible; full normalized records preserve supplied payloads and source sequence. Text rendering prevents model/trace payloads becoming HTML. Edits hide stale results and disable export until recomputed. JSON export is the actual current complete report.

Clock agreement and instrumentation coverage are assumptions. Busy union is not CPU busy time; uncovered span is not proven idle time; peak spans is not core/worker utilization; overlap is not wasted work. Parent context is not a causal dependency graph. No automatic bottleneck diagnosis, causal critical path, latency prediction or quality claim is made.

## Verification

All 33 original tests, baseline/candidate traces and demo are byte-preserved and fingerprinted. Original README, original analysis, trace and HTML report stay visible. Original analysis/report reproduction is checked.

- 57 Python tests on 3.10-3.13. All 11,110 interval lists of lengths 1..4 on a four-point integer grid are checked against separate unit-cell coverage/concurrency, including zeros; 5,000-deep chains, cycles, forward references, mixed timestamps, nonfinite/duplicate input, invalid status/gates and p95 controls.
- 24 complete reports independently compared in JavaScript at all 2,060 numeric and 2,463 other scalar leaves.
- Actual Chrome verifies all 26 runs, 118 endpoint rows, 93 segments, 85 paths/full displayed records, 32 parent-time relations, 81 timeline marks, p95 rows, export/invalidation and 320/390/1280 containment.
- Isolated installed wheel outside the checkout verifies eleven module origins, every report and audit/validate/analyze/report/compare CLI with JSON/HTML/JUnit/Markdown/SARIF.

Browser audit bounds are 16 events/four runs, integer durations <=1,000,000ms, tokens <=1,000,000, six-decimal costs in [0,1], restricted UTC timestamps (2000..2100) and bounded ASCII/integer payloads. Native analysis has broader input limits. Same-environment byte regeneration is not universal cross-platform determinism. See [EVIDENCE.md](EVIDENCE.md).

```bash
python -m unittest discover -s tests -v
python tools/build_audits.py
npm test
bash tools/wheel_smoke.sh
```
