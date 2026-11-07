from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from . import __version__
from .analysis import analyze_steps
from .compare import compare_results
from .parser import load_trace
from .report import render_junit, render_markdown, render_report, render_sarif


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
    if args.junit:
        Path(args.junit).write_text(render_junit(result), encoding="utf-8")
    if args.markdown:
        Path(args.markdown).write_text(render_markdown(result), encoding="utf-8")
    if args.sarif:
        Path(args.sarif).write_text(render_sarif(result, version=__version__, trace_path=args.trace), encoding="utf-8")
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


def _fmt_metric(metric: str, value: float) -> str:
    if metric == "cost_usd":
        return f"${value:.6f}"
    if metric == "max_p95_ms":
        return f"{value:.3f} ms"
    return f"{value:g}"


def cmd_compare(args) -> int:
    baseline_data = _load(args.baseline)
    candidate_data = _load(args.candidate)
    baseline = analyze_steps(baseline_data.steps, baseline_data.issues)
    candidate = analyze_steps(candidate_data.steps, candidate_data.issues)
    result = compare_results(
        baseline,
        candidate,
        max_new_errors=args.max_new_errors,
        max_step_increase_pct=args.max_step_increase_pct,
        max_p95_increase_ms=args.max_p95_increase_ms,
        max_cost_increase_pct=args.max_cost_increase_pct,
        max_repeat_increase=args.max_repeat_increase,
    )
    payload = result.to_dict()
    if args.out:
        Path(args.out).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for delta in result.deltas:
        pct = "n/a" if delta.delta_pct is None else f"{delta.delta_pct:+.3f}%"
        print(
            f"{delta.metric}: {_fmt_metric(delta.metric, delta.baseline)} -> "
            f"{_fmt_metric(delta.metric, delta.candidate)} "
            f"({_fmt_metric(delta.metric, delta.delta)}, {pct})"
        )
    for issue in baseline.issues:
        print(f"WARN baseline: {issue}")
    for issue in candidate.issues:
        print(f"WARN candidate: {issue}")
    if result.gate_failures:
        for failure in result.gate_failures:
            print(f"FAIL {failure}")
        return 1
    print("OK comparison gates passed")
    return 0 if not baseline.issues and not candidate.issues else 1


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
    analyze.add_argument("--junit", help="write analysis results as JUnit XML")
    analyze.add_argument("--markdown", help="write a Markdown CI job summary")
    analyze.add_argument("--sarif", help="write SARIF 2.1.0 output for code-scanning tools")
    gates(analyze)
    analyze.set_defaults(func=cmd_analyze)
    report = sub.add_parser("report", help="render a standalone HTML report")
    report.add_argument("trace")
    report.add_argument("--out", required=True)
    gates(report)
    report.set_defaults(func=cmd_report)

    compare = sub.add_parser("compare", help="compare two traces and gate regressions")
    compare.add_argument("baseline")
    compare.add_argument("candidate")
    compare.add_argument("--json", dest="out", help="write comparison JSON")
    compare.add_argument("--max-new-errors", type=int, default=0, help="allowed increase in failed/error steps")
    compare.add_argument("--max-step-increase-pct", type=float, help="allowed step-count increase percentage")
    compare.add_argument("--max-p95-increase-ms", type=float, help="allowed increase in max p95 step latency")
    compare.add_argument("--max-cost-increase-pct", type=float, help="allowed cost increase percentage")
    compare.add_argument("--max-repeat-increase", type=int, help="allowed increase in max repeated step signature count")
    compare.set_defaults(func=cmd_compare)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
