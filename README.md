# agenttrace

I kept staring at JSONL logs from agent runs trying to figure out where the time actually went, so I wrote this. It reads a trace, checks that it's well formed (parents resolve, no cycles, no duplicate steps), and tells you step counts, errors, loops, tokens, cost and latency. Python standard library only.

## Quick start

```bash
python -m agenttrace validate examples/trace.jsonl
python -m agenttrace analyze examples/trace.jsonl --fail-on-error --max-p95-ms 500
python -m agenttrace report examples/trace.jsonl --out report.html
python -m agenttrace compare examples/trace.jsonl examples/trace_candidate.jsonl --max-new-errors 0
```

On the example trace `analyze` prints `1 run(s), 5 steps, 0 errors, 2 tool calls, 2 LLM calls, $0.004500`. `compare` on the two example traces shows the candidate's p95 going from 212 ms to 272 ms and cost up 33%, still inside the gates. The example traces are synthetic, I made them up for testing.

Each event needs `run_id`, `step`, `kind` (llm, tool, action, observation, error) and `name`. Optional fields: parent id, `started_at`, `duration_ms`, token counts, `cost_usd`, and whatever input/output payload you want to keep. Reports can be JSON, HTML, JUnit, Markdown or SARIF.

## Things worth knowing

Adding up step durations isn't the same as elapsed time once steps overlap, so the timing view shows actual wall-clock coverage and overlap separately. A parent link also doesn't mean the child waited on the parent, so I don't call anything a critical path.

The browser version lets you edit events and see the timeline: https://midya8.github.io/agenttrace/

There's a side experiment in `capacity.html` / `agenttrace-capacity` about which intervals you'd drop under a concurrency cap. It's described in CAPACITY.md and doesn't touch the main analyzer.

## Tests

```bash
python -m unittest discover -s tests
npm test   # browser tests, needs Chrome
```
