from __future__ import annotations

from collections import defaultdict
from html import escape
from typing import Iterable
import xml.etree.ElementTree as ET

from .analysis import AnalysisResult
from .models import TraceStep

_CSS = """
:root{color-scheme:light;font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif;background:#f4f6f9;color:#17202a}
body{margin:0;padding:40px}main{max-width:1180px;margin:auto}h1{font-size:40px;margin:0 0 6px}h2{margin-top:30px}.muted{color:#667085}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px;margin:24px 0}.card,.panel{background:white;border:1px solid #dde3ec;border-radius:14px;box-shadow:0 4px 18px #1018280d}.card{padding:18px}.value{font-size:27px;font-weight:800}.panel{padding:0;overflow:hidden}table{width:100%;border-collapse:collapse}th,td{padding:11px 13px;border-bottom:1px solid #e8edf3;text-align:left;vertical-align:top}th{background:#f8fafc;color:#475467;font-size:12px;text-transform:uppercase;letter-spacing:.05em}.bad{color:#b42318;font-weight:700}.ok{color:#067647;font-weight:700}.timeline{padding:18px}.bar-row{display:grid;grid-template-columns:230px 1fr 120px;gap:12px;align-items:center;margin:9px 0}.track{height:18px;background:#eef2f6;border-radius:8px;position:relative}.bar{height:18px;border-radius:8px;background:#2e90fa;min-width:2px}.bar.failed{background:#f04438}.bar.llm{background:#7a5af8}.bar.tool{background:#12b76a}code{background:#f2f4f7;border-radius:5px;padding:2px 5px}
"""


def _card(label: str, value: object, note: str = "") -> str:
    return f'<section class="card"><div class="value">{escape(str(value))}</div><div>{escape(label)}</div><div class="muted">{escape(note)}</div></section>'


def render_report(steps: Iterable[TraceStep], result: AnalysisResult) -> str:
    steps = tuple(steps)
    totals = result.to_dict()["totals"]
    cards = "".join([
        _card("runs", totals["runs"]),
        _card("steps", totals["steps"]),
        _card("errors", totals["errors"]),
        _card("tool calls", totals["tool_calls"]),
        _card("LLM calls", totals["llm_calls"]),
        _card("cost", f"${totals['cost_usd']:.6f}"),
    ])
    issue_items = "".join(f"<li>{escape(issue)}</li>" for issue in (*result.issues, *result.gate_failures)) or "<li>No validation or gate issues.</li>"
    run_rows = "".join(
        "<tr>"
        f"<td>{escape(run.run_id)}</td><td>{run.steps}</td><td class={'bad' if run.errors else 'ok'}>{run.errors}</td>"
        f"<td>{run.tool_calls}</td><td>{run.llm_calls}</td><td>{run.max_repeat}</td><td>{run.max_depth}</td>"
        f"<td>{run.p95_step_ms:.1f} ms</td><td>{run.tokens_input + run.tokens_output}</td><td>${run.cost_usd:.6f}</td>"
        "</tr>"
        for run in result.runs
    )
    timeline_parts: list[str] = []
    grouped: dict[str, list[TraceStep]] = defaultdict(list)
    for step in steps:
        grouped[step.run_id].append(step)
    for run_id, run_steps in sorted(grouped.items()):
        starts = [step.started for step in run_steps if step.started]
        origin = min(starts) if starts else None
        total = max(sum(step.duration_ms for step in run_steps), 1.0)
        rows = []
        for step in sorted(run_steps, key=lambda item: item.sequence):
            offset = (step.started - origin).total_seconds() * 1000 if origin and step.started else 0.0
            left = min(95.0, offset / total * 100)
            width = max(0.5, min(100 - left, step.duration_ms / total * 100))
            classes = f"bar {escape(step.kind)}{' failed' if step.failed else ''}"
            rows.append(
                '<div class="bar-row">'
                f'<div><code>{escape(step.step)}</code> {escape(step.name)}</div>'
                f'<div class="track"><div class="{classes}" style="left:{left:.3f}%;width:{width:.3f}%"></div></div>'
                f'<div>{step.duration_ms:.1f} ms</div></div>'
            )
        timeline_parts.append(f"<h3>{escape(run_id)}</h3>" + "".join(rows))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AgentTrace report</title><style>{_CSS}</style></head>
<body><main><h1>AgentTrace report</h1><p class="muted">Local-first trace analysis for AI agent runs.</p><section class="cards">{cards}</section>
<h2>Run summary</h2><section class="panel"><table><thead><tr><th>Run</th><th>Steps</th><th>Errors</th><th>Tools</th><th>LLM</th><th>Max repeat</th><th>Depth</th><th>p95 step</th><th>Tokens</th><th>Cost</th></tr></thead><tbody>{run_rows}</tbody></table></section>
<h2>Validation and gates</h2><section class="panel"><ul>{issue_items}</ul></section>
<h2>Step timeline</h2><section class="panel timeline">{''.join(timeline_parts)}</section>
</main></body></html>"""


def render_junit(result: AnalysisResult) -> str:
    """Render analysis results as a JUnit XML suite for CI test viewers."""
    checks = 1 + len(result.runs)
    failures = len([run for run in result.runs if run.errors])
    if result.issues or result.gate_failures:
        failures += 1
    total_seconds = sum(run.duration_ms for run in result.runs) / 1000.0
    suite = ET.Element(
        "testsuite",
        {
            "name": "agenttrace",
            "tests": str(checks),
            "failures": str(failures),
            "errors": "0",
            "time": f"{total_seconds:.6f}",
        },
    )
    gate_case = ET.SubElement(
        suite,
        "testcase",
        {"classname": "agenttrace", "name": "analysis validation and gates", "time": "0.000000"},
    )
    if result.issues or result.gate_failures:
        detail = "\n".join((*result.issues, *result.gate_failures))
        element = ET.SubElement(gate_case, "failure", {"message": "analysis validation or gates failed"})
        element.text = detail
    for run in result.runs:
        testcase = ET.SubElement(
            suite,
            "testcase",
            {
                "classname": "agenttrace.run",
                "name": run.run_id,
                "time": f"{run.duration_ms / 1000.0:.6f}",
            },
        )
        if run.errors:
            element = ET.SubElement(
                testcase,
                "failure",
                {"message": f"run has {run.errors} failed/error step(s)"},
            )
            element.text = (
                f"steps={run.steps}; errors={run.errors}; tool_calls={run.tool_calls}; "
                f"llm_calls={run.llm_calls}; max_repeat={run.max_repeat}; "
                f"p95_step_ms={run.p95_step_ms:.3f}; cost_usd={run.cost_usd:.8f}"
            )
    ET.indent(suite, space="  ")
    return "<?xml version='1.0' encoding='utf-8'?>\n" + ET.tostring(suite, encoding="unicode") + "\n"
