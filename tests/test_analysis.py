import unittest

from agenttrace.analysis import analyze_steps, percentile
from agenttrace.parser import parse_lines


def event(step, kind="tool", name="search", status="ok", duration=10, cost=0.0, payload=None, parent=None):
    import json
    record = {
        "run_id": "run",
        "step": step,
        "parent": parent,
        "kind": kind,
        "name": name,
        "status": status,
        "duration_ms": duration,
        "cost_usd": cost,
        "input": payload if payload is not None else {"q": step},
    }
    return json.dumps(record)


class AnalysisTests(unittest.TestCase):
    def test_percentile_interpolates(self):
        self.assertEqual(10, percentile([10], 95))
        self.assertAlmostEqual(19.5, percentile([10, 20], 95))

    def test_run_summary_counts(self):
        lines = [
            event("plan", kind="llm", name="planner", duration=100, cost=0.01),
            event("tool", duration=20, parent="plan"),
            event("done", kind="observation", duration=5, parent="tool"),
        ]
        data = parse_lines(lines)
        result = analyze_steps(data.steps, data.issues)
        self.assertEqual(1, len(result.runs))
        run = result.runs[0]
        self.assertEqual(3, run.steps)
        self.assertEqual(0, run.errors)
        self.assertEqual(1, run.tool_calls)
        self.assertEqual(1, run.llm_calls)
        self.assertEqual(3, run.max_depth)
        self.assertEqual(125, run.duration_ms)
        self.assertEqual(0.01, run.cost_usd)

    def test_fail_on_error_gate(self):
        data = parse_lines([event("bad", status="failed")])
        result = analyze_steps(data.steps, fail_on_error=True)
        self.assertFalse(result.ok)
        self.assertIn("failed/error", result.gate_failures[0])

    def test_error_kind_counts_as_error(self):
        data = parse_lines([event("bad", kind="error", status="ok")])
        result = analyze_steps(data.steps, fail_on_error=True)
        self.assertFalse(result.ok)
        self.assertEqual(1, result.runs[0].errors)

    def test_loop_gate(self):
        lines = [event(f"s{i}", payload={"same": True}) for i in range(4)]
        data = parse_lines(lines)
        result = analyze_steps(data.steps, max_loop_repeat=3)
        self.assertFalse(result.ok)
        self.assertIn("repeated step signature 4 times", result.gate_failures[0])

    def test_different_payloads_do_not_count_as_same_loop(self):
        lines = [event(f"s{i}", payload={"i": i}) for i in range(4)]
        data = parse_lines(lines)
        result = analyze_steps(data.steps, max_loop_repeat=3)
        self.assertTrue(result.ok)
        self.assertEqual(1, result.runs[0].max_repeat)

    def test_latency_cost_and_step_gates(self):
        data = parse_lines([event("a", duration=100, cost=0.2), event("b", duration=300, cost=0.3)])
        result = analyze_steps(data.steps, max_p95_ms=200, max_cost_usd=0.4, max_steps=1)
        self.assertEqual(3, len(result.gate_failures))
        text = "\n".join(result.gate_failures)
        self.assertIn("p95", text)
        self.assertIn("cost", text)
        self.assertIn("steps", text)

    def test_json_shape(self):
        data = parse_lines([event("a")])
        payload = analyze_steps(data.steps).to_dict()
        self.assertEqual(1, payload["schema_version"])
        self.assertTrue(payload["ok"])
        self.assertEqual(1, payload["totals"]["runs"])
        self.assertEqual("run", payload["runs"][0]["run_id"])


if __name__ == "__main__":
    unittest.main()
