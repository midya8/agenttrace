from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .analysis import analyze_steps
from .parser import load_trace
from .report import render_report


def _load(path: str):
    try:
        return load_trace(path)
    except OSError as exc:
        raise SystemExit(f"agenttrace: cannot read {path}: {exc}")


def _analysis(args) -> tuple[object, object]:
    data = _load(args.trace)
    result = analyze_steps(
        data.steps,
        data.issues,
        fail_on_error=getattr(args, "fail_on_error", False),
        max_loop_repeat=getattr(args, "max_loop_repeat", 3),
        max_p95_ms=getattr(args, "max_p95_ms", None),
        max_cost_usd=getattr(args, "max_cost_usd", None),
        max_steps=getattr(args, "max_steps", None),
    )
    return data, result


def cmd_validate(args) -> int:
    data = _load(args.trace)
    if data.issues:
        for issue in data.issues:
            print(f"ERROR {issue}")
        print(f"{len(data.steps)} valid step(s), {len(data.issues)} issue(s)")
        return 1
    print(f"OK {len(data.steps)} trace step(s) across {len({step.run_id for step in data.steps})} run(s)")
    return 0


def cmd_analyze(args) -> int:
    data, result = _analysis(args)
    payload = result.to_dict()
    if args.out:
        Path(args.out).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    totals = payload["totals"]
    print(
        f"{totals['runs']} run(s), {totals['steps']} steps, {totals['errors']} errors, "
        f"{totals['tool_calls']} tool calls, {totals['llm_calls']} LLM calls, ${totals['cost_usd']:.6f}"
    )
    for issue in result.issues:
        print(f"WARN {issue}")
    if result.gate_failures:
        for failure in result.gate_failures:
            print(f"FAIL {failure}")
        return 1
    print("OK analysis gates passed")
    return 0 if not data.issues else 1


def cmd_report(args) -> int:
    data, result = _analysis(args)
    html = render_report(data.steps, result)
    Path(args.out).write_text(html, encoding="utf-8")
    print(f"wrote {args.out}")
    return 0 if result.ok and not data.issues else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agenttrace", description="Validate, analyze and report AI agent traces.")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="validate a JSONL trace")
    validate.add_argument("trace")
    validate.set_defaults(func=cmd_validate)

    def gates(p):
        p.add_argument("--fail-on-error", action="store_true", help="fail when any trace step failed")
        p.add_argument("--max-loop-repeat", type=int, default=3, help="maximum allowed repeats of the same step signature")
        p.add_argument("--max-p95-ms", type=float, help="maximum allowed p95 step latency")
        p.add_argument("--max-cost-usd", type=float, help="maximum allowed trace cost per run")
        p.add_argument("--max-steps", type=int, help="maximum allowed steps per run")

    analyze = sub.add_parser("analyze", help="summarize runs and enforce gates")
    analyze.add_argument("trace")
    analyze.add_argument("--json", dest="out", help="write analysis JSON")
    gates(analyze)
    analyze.set_defaults(func=cmd_analyze)
    report = sub.add_parser("report", help="render a standalone HTML report")
    report.add_argument("trace")
    report.add_argument("--out", required=True)
    gates(report)
    report.set_defaults(func=cmd_report)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
