from __future__ import annotations

from dataclasses import dataclass

from .analysis import AnalysisResult


_METRIC_ORDER = (
    "runs",
    "steps",
    "errors",
    "tool_calls",
    "llm_calls",
    "max_repeat",
    "max_p95_ms",
    "tokens_input",
    "tokens_output",
    "cost_usd",
)


@dataclass(frozen=True)
class MetricDelta:
    metric: str
    baseline: float
    candidate: float
    delta: float
    delta_pct: float | None

    def to_dict(self) -> dict[str, object]:
        return {
            "metric": self.metric,
            "baseline": self.baseline,
            "candidate": self.candidate,
            "delta": self.delta,
            "delta_pct": self.delta_pct,
        }


@dataclass(frozen=True)
class CompareResult:
    baseline: dict[str, float]
    candidate: dict[str, float]
    deltas: tuple[MetricDelta, ...]
    gate_failures: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.gate_failures

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "ok": self.ok,
            "baseline": self.baseline,
            "candidate": self.candidate,
            "deltas": [delta.to_dict() for delta in self.deltas],
            "gate_failures": list(self.gate_failures),
        }


def _metrics(result: AnalysisResult) -> dict[str, float]:
    totals = result.to_dict()["totals"]
    return {
        "runs": float(totals["runs"]),
        "steps": float(totals["steps"]),
        "errors": float(totals["errors"]),
        "tool_calls": float(totals["tool_calls"]),
        "llm_calls": float(totals["llm_calls"]),
        "max_repeat": float(max((run.max_repeat for run in result.runs), default=0)),
        "max_p95_ms": float(max((run.p95_step_ms for run in result.runs), default=0.0)),
        "tokens_input": float(totals["tokens_input"]),
        "tokens_output": float(totals["tokens_output"]),
        "cost_usd": float(totals["cost_usd"]),
    }


def _pct_change(baseline: float, delta: float) -> float | None:
    if baseline == 0:
        return None
    return delta / baseline * 100


def compare_results(
    baseline: AnalysisResult,
    candidate: AnalysisResult,
    *,
    max_new_errors: int = 0,
    max_step_increase_pct: float | None = None,
    max_p95_increase_ms: float | None = None,
    max_cost_increase_pct: float | None = None,
    max_repeat_increase: int | None = None,
) -> CompareResult:
    import math
    for key,value,integer in [('max_new_errors',max_new_errors,True),('max_step_increase_pct',max_step_increase_pct,False),('max_p95_increase_ms',max_p95_increase_ms,False),('max_cost_increase_pct',max_cost_increase_pct,False),('max_repeat_increase',max_repeat_increase,True)]:
        if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float)) or (integer and not isinstance(value,int)) or not math.isfinite(value) or value<0):raise ValueError(key+' must be finite, nonnegative and correctly typed')
    before = _metrics(baseline)
    after = _metrics(candidate)
    deltas = tuple(
        MetricDelta(
            metric=metric,
            baseline=before[metric],
            candidate=after[metric],
            delta=after[metric] - before[metric],
            delta_pct=_pct_change(before[metric], after[metric] - before[metric]),
        )
        for metric in _METRIC_ORDER
    )
    by_metric = {delta.metric: delta for delta in deltas}
    failures: list[str] = [f"{side} trace invalid: {issue}" for side,r in [("baseline",baseline),("candidate",candidate)] for issue in r.issues]
    if by_metric["errors"].delta > max_new_errors:
        failures.append(f"new errors increased by {by_metric['errors'].delta:g} (> {max_new_errors})")
    step_delta = by_metric["steps"]
    if max_step_increase_pct is not None and step_delta.delta > 0:
        pct = step_delta.delta_pct if step_delta.delta_pct is not None else float("inf")
        if pct > max_step_increase_pct:
            failures.append(f"step count increased by {pct:.3f}% (> {max_step_increase_pct}%)")
    p95_delta = by_metric["max_p95_ms"]
    if max_p95_increase_ms is not None and p95_delta.delta > max_p95_increase_ms:
        failures.append(f"max p95 step latency increased by {p95_delta.delta:.3f} ms (> {max_p95_increase_ms})")
    cost_delta = by_metric["cost_usd"]
    if max_cost_increase_pct is not None and cost_delta.delta > 0:
        pct = cost_delta.delta_pct if cost_delta.delta_pct is not None else float("inf")
        if pct > max_cost_increase_pct:
            failures.append(f"cost increased by {pct:.3f}% (> {max_cost_increase_pct}%)")
    repeat_delta = by_metric["max_repeat"]
    if max_repeat_increase is not None and repeat_delta.delta > max_repeat_increase:
        failures.append(f"max repeated step count increased by {repeat_delta.delta:g} (> {max_repeat_increase})")
    return CompareResult(before, after, deltas, tuple(failures))
