import json
import os
from pathlib import Path
import tempfile
import unittest

from agenttrace.cli import main
from agenttrace.report import render_report
from agenttrace.parser import parse_lines
from agenttrace.analysis import analyze_steps


class CliTests(unittest.TestCase):
    def write(self, directory, text):
        path = Path(directory) / "trace.jsonl"
        path.write_text(text, encoding="utf-8")
        return str(path)

    def test_validate_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = self.write(tmp, '{"run_id":"r","step":"a","kind":"llm","name":"planner"}\n')
            self.assertEqual(0, main(["validate", trace]))

    def test_validate_bad(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = self.write(tmp, '{bad}\n')
            self.assertEqual(1, main(["validate", trace]))

    def test_analyze_writes_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = self.write(tmp, '{"run_id":"r","step":"a","kind":"llm","name":"planner"}\n')
            out = Path(tmp) / "analysis.json"
            self.assertEqual(0, main(["analyze", trace, "--json", str(out)]))
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertTrue(payload["ok"])
            self.assertEqual(1, payload["totals"]["steps"])

    def test_analyze_gate_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = self.write(tmp, '{"run_id":"r","step":"a","kind":"llm","name":"planner","status":"failed"}\n')
            self.assertEqual(1, main(["analyze", trace, "--fail-on-error"]))

    def test_report_writes_escaped_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = self.write(tmp, '{"run_id":"r","step":"a","kind":"llm","name":"<script>alert(1)</script>"}\n')
            out = Path(tmp) / "report.html"
            self.assertEqual(0, main(["report", trace, "--out", str(out)]))
            html = out.read_text(encoding="utf-8")
            self.assertIn("AgentTrace report", html)
            self.assertNotIn("<script>alert(1)</script>", html)
            self.assertIn("&lt;script&gt;", html)

    def test_missing_file_is_system_exit(self):
        with self.assertRaises(SystemExit):
            main(["validate", "/definitely/not/here.jsonl"])

    def test_report_includes_run_table(self):
        data = parse_lines(['{"run_id":"r","step":"a","kind":"tool","name":"search","duration_ms":4}\n'])
        result = analyze_steps(data.steps, data.issues)
        html = render_report(data.steps, result)
        self.assertIn("Run summary", html)
        self.assertIn("Step timeline", html)
        self.assertIn("search", html)


if __name__ == "__main__":
    unittest.main()
