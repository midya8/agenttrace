from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any

VALID_KINDS = {"llm", "tool", "action", "observation", "error"}
VALID_STATUSES = {"ok", "failed", "cancelled", "timeout"}


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


@dataclass(frozen=True)
class TraceStep:
    run_id: str
    step: str
    parent: str | None
    kind: str
    name: str
    status: str
    started_at: str | None
    duration_ms: float
    tokens_input: int
    tokens_output: int
    cost_usd: float
    input: Any
    output: Any
    sequence: int

    @property
    def started(self) -> datetime | None:
        return parse_time(self.started_at)

    @property
    def total_tokens(self) -> int:
        return self.tokens_input + self.tokens_output

    @property
    def failed(self) -> bool:
        return self.status != "ok" or self.kind == "error"

    @property
    def signature(self) -> str:
        try:
            payload = json.dumps(self.input, sort_keys=True, separators=(",", ":"), default=str)
        except (TypeError, ValueError):
            payload = repr(self.input)
        return f"{self.kind}:{self.name}:{payload}"


@dataclass(frozen=True)
class TraceData:
    steps: tuple[TraceStep, ...]
    issues: tuple[str, ...]
