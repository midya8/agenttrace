import json
from pathlib import Path
import tempfile
import unittest

from agenttrace.analysis import analyze_steps
from agenttrace.cli import main
from agenttrace.compare import compare_results
from agenttrace.parser import parse_lines


def trace(step="a", status="ok", duration=10, cost=0.01):
    return json.dumps(
        {
            "run_id": "run",
            "step": step,
            "kind": "llm",
            "name": "planner",
            "status": status,
            "duration_ms": duration,
            "cost_usd": cost,
        }
    )


def analysis(*lines):
    data = parse_lines(lines)
    return analyze_steps(data.steps, data.issues)


class CompareTests(unittest.TestCase):
    def test_metric_deltas_include_percentages(self):
        baseline = analysis(trace(duration=100, cost=0.10))
        candidate = analysis(trace(duration=150, cost=0.15))
        result = compare_results(baseline, candidate)
        by_metric = {delta.metric: delta for delta in result.deltas}
        self.assertTrue(result.ok)
        self.assertEqual(50.0, by_metric["max_p95_ms"].delta)
        self.assertEqual(50.0, by_metric["max_p95_ms"].delta_pct)
        self.assertAlmostEqual(50.0, by_metric["cost_usd"].delta_pct)

    def test_new_errors_fail_by_default(self):
        baseline = analysis(trace())
        candidate = analysis(trace(status="failed"))
        result = compare_results(baseline, candidate)
        self.assertFalse(result.ok)
        self.assertIn("new errors increased by 1", result.gate_failures[0])

    def test_thresholds_gate_cost_latency_steps_and_repeats(self):
        baseline = analysis(trace(duration=100, cost=0.10))
        candidate_lines = [trace(step=str(i), duration=200, cost=0.20) for i in range(3)]
        candidate = analysis(*candidate_lines)
        result = compare_results(
            baseline,
            candidate,
            max_step_increase_pct=100,
            max_p95_increase_ms=50,
            max_cost_increase_pct=50,
            max_repeat_increase=0,
        )
        self.assertFalse(result.ok)
        text = "\n".join(result.gate_failures)
        self.assertIn("step count increased", text)
        self.assertIn("max p95 step latency increased", text)
        self.assertIn("cost increased", text)

    def test_regressions_can_improve_without_failing(self):
        baseline = analysis(trace(status="failed", duration=200, cost=0.20))
        candidate = analysis(trace(duration=100, cost=0.10))
        result = compare_results(
            baseline,
            candidate,
            max_step_increase_pct=0,
            max_p95_increase_ms=0,
            max_cost_increase_pct=0,
        )
        self.assertTrue(result.ok)

    def test_cli_compare_writes_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            baseline_path = Path(tmp) / "baseline.jsonl"
            candidate_path = Path(tmp) / "candidate.jsonl"
            out = Path(tmp) / "compare.json"
            baseline_path.write_text(trace(duration=100) + "\n", encoding="utf-8")
            candidate_path.write_text(trace(duration=120) + "\n", encoding="utf-8")
            code = main(
                [
                    "compare",
                    str(baseline_path),
                    str(candidate_path),
                    "--max-p95-increase-ms",
                    "50",
                    "--json",
                    str(out),
                ]
            )
            self.assertEqual(0, code)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertTrue(payload["ok"])
            self.assertEqual(20.0, payload["candidate"]["max_p95_ms"] - payload["baseline"]["max_p95_ms"])


if __name__ == "__main__":
    unittest.main()
