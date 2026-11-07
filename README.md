# AgentTrace

Local-first validation, analysis, and HTML reporting for AI agent execution traces.

AgentTrace reads JSONL agent traces, checks their structure, summarizes every run, detects repeated tool/action loops, tracks failures, latency, tokens and cost, enforces CI-friendly gates, and renders a standalone HTML timeline. It is dependency-free and works offline, so it can inspect traces from local agents, test fixtures, internal tools, or hosted model adapters without sending prompts or outputs anywhere.

## Why

Agent frameworks are good at showing a friendly final answer and bad at preserving the operational truth of how it got there. AgentTrace keeps that truth in a portable record:

- every LLM call, tool call, action, observation and error is one JSONL event;
- every run can be validated before analysis;
- loops and repeated calls are detected from kind, name and normalized input;
- errors, p95 step latency, run depth, token totals and cost are explicit;
- thresholds turn trace review into a scriptable quality gate;
- escaped HTML reports make the run reviewable without a server, JavaScript bundle, or external service.

## Trace format

Each line is one JSON object. Required fields are `run_id`, `step`, `kind` and `name`.

```json
{"run_id":"research-demo","step":"search","parent":"plan","kind":"tool","name":"repo.search","status":"ok","started_at":"2026-11-07T05:00:00.200Z","duration_ms":95,"input":{"query":"evaluation harness"},"output":{"matches":8}}
```

Supported `kind` values are `llm`, `tool`, `action`, `observation` and `error`. Supported statuses are `ok`, `failed`, `cancelled` and `timeout`. Optional numeric fields are `duration_ms`, `tokens_input`, `tokens_output` and `cost_usd`; optional payloads are `input` and `output`; `parent` links a step to an earlier step in the same run.

## Commands

Validate a trace:

```bash
python3 -m agenttrace validate examples/trace.jsonl
```

Analyze runs and write a JSON summary:

```bash
python3 -m agenttrace analyze examples/trace.jsonl --json analysis.json
```

Enforce quality gates:

```bash
python3 -m agenttrace analyze examples/trace.jsonl \
  --fail-on-error \
  --max-loop-repeat 3 \
  --max-p95-ms 500 \
  --max-cost-usd 0.01 \
  --max-steps 10
```

Render a standalone report:

```bash
python3 -m agenttrace report examples/trace.jsonl --out report.html
```

## Offline demo

The demo uses a fixed local trace fixture. It demonstrates validation, analysis, gates and report rendering without any model/API call:

```bash
bash examples/demo.sh
```

The fixture currently covers a five-step agent run with planning, two tool calls, writing and a final observation. Its timing and cost numbers are fixture data, not evidence about a real model.

## Development

```bash
python3 -m unittest discover -s tests -v
bash examples/demo.sh
```

The test suite runs fully offline. CI runs the same checks on Python 3.10 through 3.13.

## Design notes

- **Portable input:** JSONL is easy for agents and test harnesses to append and for Unix tools to inspect.
- **Validation first:** malformed events, duplicate step IDs, unknown parents, negative numbers, unknown event types and bad timestamps are reported before analysis is trusted.
- **Loop detection:** repeated signatures use event kind, name and normalized input payload, so retries with changed arguments do not count as the same loop.
- **Reviewable output:** the report escapes untrusted trace payloads, needs no JavaScript, and can be archived with the run.
- **Scriptable gates:** meaningful exit codes let CI fail on agent errors, loops, high latency, high cost or oversized runs.
