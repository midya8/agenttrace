from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Iterable

from .models import TraceStep


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * pct / 100
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


@dataclass(frozen=True)
class RunAnalysis:
    run_id: str
    steps: int
    errors: int
    tool_calls: int
    llm_calls: int
    repeated_signatures: int
    max_repeat: int
    max_depth: int
    duration_ms: float
    p95_step_ms: float
    tokens_input: int
    tokens_output: int
    cost_usd: float

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "steps": self.steps,
            "errors": self.errors,
            "tool_calls": self.tool_calls,
            "llm_calls": self.llm_calls,
            "repeated_signatures": self.repeated_signatures,
            "max_repeat": self.max_repeat,
            "max_depth": self.max_depth,
            "duration_ms": round(self.duration_ms, 3),
            "p95_step_ms": round(self.p95_step_ms, 3),
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "cost_usd": round(self.cost_usd, 8),
        }


@dataclass(frozen=True)
class AnalysisResult:
    runs: tuple[RunAnalysis, ...]
    issues: tuple[str, ...] = field(default_factory=tuple)
    gate_failures: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return not self.gate_failures

    def to_dict(self) -> dict[str, object]:
        totals = {
            "runs": len(self.runs),
            "steps": sum(run.steps for run in self.runs),
            "errors": sum(run.errors for run in self.runs),
            "tool_calls": sum(run.tool_calls for run in self.runs),
            "llm_calls": sum(run.llm_calls for run in self.runs),
            "tokens_input": sum(run.tokens_input for run in self.runs),
            "tokens_output": sum(run.tokens_output for run in self.runs),
            "cost_usd": round(sum(run.cost_usd for run in self.runs), 8),
        }
        return {
            "schema_version": 1,
            "ok": self.ok,
            "totals": totals,
            "runs": [run.to_dict() for run in self.runs],
            "issues": list(self.issues),
            "gate_failures": list(self.gate_failures),
        }


def _depths(steps: Iterable[TraceStep]) -> int:
    by_id = {step.step: step for step in steps}
    memo: dict[str, int] = {}

    def depth(step: TraceStep, visiting: set[str] | None = None) -> int:
        if step.step in memo:
            return memo[step.step]
        visiting = visiting or set()
        if step.step in visiting or not step.parent or step.parent not in by_id:
            memo[step.step] = 1
        else:
            memo[step.step] = 1 + depth(by_id[step.parent], visiting | {step.step})
        return memo[step.step]

    return max((depth(step) for step in steps), default=0)


def analyze_steps(
    steps: Iterable[TraceStep],
    parser_issues: Iterable[str] = (),
    *,
    fail_on_error: bool = False,
    max_loop_repeat: int = 3,
    max_p95_ms: float | None = None,
    max_cost_usd: float | None = None,
    max_steps: int | None = None,
) -> AnalysisResult:
    grouped: dict[str, list[TraceStep]] = defaultdict(list)
    for step in steps:
        grouped[step.run_id].append(step)
    runs: list[RunAnalysis] = []
    failures: list[str] = []
    for run_id in sorted(grouped):
        run_steps = sorted(grouped[run_id], key=lambda item: (item.started or item.started is not None, item.sequence))
        signatures = Counter(step.signature for step in run_steps)
        repeated = [count for count in signatures.values() if count > 1]
        errors = sum(step.failed for step in run_steps)
        durations = [step.duration_ms for step in run_steps]
        analysis = RunAnalysis(
            run_id=run_id,
            steps=len(run_steps),
            errors=errors,
            tool_calls=sum(step.kind == "tool" for step in run_steps),
            llm_calls=sum(step.kind == "llm" for step in run_steps),
            repeated_signatures=len(repeated),
            max_repeat=max(signatures.values(), default=0),
            max_depth=_depths(run_steps),
            duration_ms=sum(durations),
            p95_step_ms=percentile(durations, 95),
            tokens_input=sum(step.tokens_input for step in run_steps),
            tokens_output=sum(step.tokens_output for step in run_steps),
            cost_usd=sum(step.cost_usd for step in run_steps),
        )
        runs.append(analysis)
        if fail_on_error and errors:
            failures.append(f"run {run_id}: {errors} failed/error step(s)")
        if max_loop_repeat >= 0 and analysis.max_repeat > max_loop_repeat:
            failures.append(f"run {run_id}: repeated step signature {analysis.max_repeat} times (> {max_loop_repeat})")
        if max_p95_ms is not None and analysis.p95_step_ms > max_p95_ms:
            failures.append(f"run {run_id}: p95 step latency {analysis.p95_step_ms:.3f} ms (> {max_p95_ms})")
        if max_cost_usd is not None and analysis.cost_usd > max_cost_usd:
            failures.append(f"run {run_id}: cost ${analysis.cost_usd:.6f} (> ${max_cost_usd})")
        if max_steps is not None and analysis.steps > max_steps:
            failures.append(f"run {run_id}: {analysis.steps} steps (> {max_steps})")
    return AnalysisResult(tuple(runs), tuple(parser_issues), tuple(failures))
