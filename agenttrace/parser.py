from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .models import TraceData, TraceStep, VALID_KINDS, VALID_STATUSES, parse_time

_REQUIRED = ("run_id", "step", "kind", "name")


def _number(record: dict[str, Any], key: str, default: float, issues: list[str], line: int) -> float:
    value = record.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        issues.append(f"line {line}: {key} must be a number")
        return default
    if value < 0:
        issues.append(f"line {line}: {key} must be non-negative")
        return default
    return float(value)


def _integer(record: dict[str, Any], key: str, issues: list[str], line: int) -> int:
    value = record.get(key, 0)
    if isinstance(value, bool) or not isinstance(value, int):
        issues.append(f"line {line}: {key} must be an integer")
        return 0
    if value < 0:
        issues.append(f"line {line}: {key} must be non-negative")
        return 0
    return value


def parse_lines(lines: Iterable[str]) -> TraceData:
    steps: list[TraceStep] = []
    issues: list[str] = []
    seen: set[tuple[str, str]] = set()
    ids_by_run: dict[str, set[str]] = {}
    pending: list[TraceStep] = []

    for line_no, raw in enumerate(lines, 1):
        if not raw.strip():
            continue
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as exc:
            issues.append(f"line {line_no}: invalid JSON: {exc.msg}")
            continue
        if not isinstance(record, dict):
            issues.append(f"line {line_no}: trace event must be a JSON object")
            continue
        missing = [key for key in _REQUIRED if not isinstance(record.get(key), str) or not record.get(key)]
        if missing:
            issues.append(f"line {line_no}: missing required field(s): {', '.join(missing)}")
            continue
        run_id = record["run_id"]
        step_id = record["step"]
        kind = record["kind"]
        status = record.get("status", "ok")
        if kind not in VALID_KINDS:
            issues.append(f"line {line_no}: unknown kind {kind!r}")
        if status not in VALID_STATUSES:
            issues.append(f"line {line_no}: unknown status {status!r}")
        started_at = record.get("started_at")
        if started_at is not None and (not isinstance(started_at, str) or parse_time(started_at) is None):
            issues.append(f"line {line_no}: started_at must be an ISO-8601 timestamp")
            started_at = None
        if (run_id, step_id) in seen:
            issues.append(f"line {line_no}: duplicate step id {step_id!r} in run {run_id!r}")
        seen.add((run_id, step_id))
        ids_by_run.setdefault(run_id, set()).add(step_id)
        parent = record.get("parent")
        if parent is not None and not isinstance(parent, str):
            issues.append(f"line {line_no}: parent must be a string or null")
            parent = None
        duration_ms = _number(record, "duration_ms", 0, issues, line_no)
        cost_usd = _number(record, "cost_usd", 0, issues, line_no)
        step = TraceStep(
            run_id=run_id,
            step=step_id,
            parent=parent,
            kind=kind,
            name=record["name"],
            status=status,
            started_at=started_at,
            duration_ms=duration_ms,
            tokens_input=_integer(record, "tokens_input", issues, line_no),
            tokens_output=_integer(record, "tokens_output", issues, line_no),
            cost_usd=cost_usd,
            input=record.get("input"),
            output=record.get("output"),
            sequence=len(pending),
        )
        pending.append(step)

    for step in pending:
        if step.parent and step.parent not in ids_by_run.get(step.run_id, set()):
            issues.append(f"line {step.sequence + 1}: unknown parent {step.parent!r} in run {step.run_id!r}")
    steps.extend(pending)
    return TraceData(tuple(steps), tuple(issues))


def load_trace(path: str | Path) -> TraceData:
    with open(path, "r", encoding="utf-8") as handle:
        return parse_lines(handle)
