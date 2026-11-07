import json
import os
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from agenttrace.cli import main
from agenttrace.report import render_markdown, render_report, render_sarif
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
            junit = Path(tmp) / "analysis.xml"
            markdown = Path(tmp) / "analysis.md"
            sarif = Path(tmp) / "analysis.sarif"
            self.assertEqual(0, main(["analyze", trace, "--json", str(out), "--junit", str(junit), "--markdown", str(markdown), "--sarif", str(sarif)]))
            sarif_payload = json.loads(sarif.read_text(encoding="utf-8"))
            sarif_run = sarif_payload["runs"][0]
            self.assertEqual("2.1.0", sarif_payload["version"])
            self.assertEqual("AgentTrace", sarif_run["tool"]["driver"]["name"])
            self.assertEqual([], sarif_run["results"])
            self.assertTrue(sarif_run["invocations"][0]["executionSuccessful"])
            payload = json.loads(out.read_text(encoding="utf-8"))
            root = ET.parse(junit).getroot()
            summary = markdown.read_text(encoding="utf-8")
            self.assertEqual(root.tag, "testsuite")
            self.assertEqual(root.attrib["tests"], "2")
            self.assertEqual(root.attrib["failures"], "0")
            self.assertEqual(len(root.findall("testcase")), 2)
            self.assertIn("# AgentTrace analysis", summary)
            self.assertIn("**Status:** PASS", summary)
            self.assertIn("| Runs | 1 |", summary)
            self.assertTrue(payload["ok"])
            self.assertEqual(1, payload["totals"]["steps"])

    def test_analyze_gate_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = self.write(tmp, '{"run_id":"r","step":"a","kind":"llm","name":"planner","status":"failed"}\n')
            self.assertEqual(1, main(["analyze", trace, "--fail-on-error"]))

    def test_analyze_writes_sarif_for_validation_and_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = self.write(
                tmp,
                '{"run_id":"r","step":"a","kind":"llm","name":"planner","status":"failed"}\n{bad}\n',
            )
            out = Path(tmp) / "analysis.sarif"
            self.assertEqual(1, main(["analyze", trace, "--sarif", str(out), "--fail-on-error"]))
            payload = json.loads(out.read_text(encoding="utf-8"))
            run = payload["runs"][0]
            rules = {rule["id"] for rule in run["tool"]["driver"]["rules"]}
            self.assertEqual({"AGENTTRACE_GATE", "AGENTTRACE_RUN_ERRORS", "AGENTTRACE_VALIDATION"}, rules)
            self.assertEqual(["error", "error", "warning"], [item["level"] for item in run["results"]])
            self.assertEqual("r", run["results"][1]["properties"]["run_id"])
            location = run["results"][0]["locations"][0]["physicalLocation"]
            self.assertEqual(trace, location["artifactLocation"]["uri"])
            self.assertFalse(run["invocations"][0]["executionSuccessful"])

    def test_sarif_render_uses_tool_version(self):
        data = parse_lines(['{"run_id":"r","step":"a","kind":"llm","name":"planner"}\n'])
        result = analyze_steps(data.steps, data.issues)
        payload = json.loads(render_sarif(result, version="0.1.0", trace_path="trace.jsonl"))
        driver = payload["runs"][0]["tool"]["driver"]
        self.assertEqual("0.1.0", driver["version"])
        self.assertEqual("https://github.com/midya8/agenttrace", driver["informationUri"])

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

    def test_markdown_escapes_table_cells(self):
        data = parse_lines(['{"run_id":"run|one","step":"a","kind":"tool","name":"search","duration_ms":4}\n'])
        result = analyze_steps(data.steps, data.issues)
        markdown = render_markdown(result)
        self.assertIn("run\\|one", markdown)
        self.assertIn("# AgentTrace analysis", markdown)

    def test_report_includes_run_table(self):
        data = parse_lines(['{"run_id":"r","step":"a","kind":"tool","name":"search","duration_ms":4}\n'])
        result = analyze_steps(data.steps, data.issues)
        html = render_report(data.steps, result)
        self.assertIn("Run summary", html)
        self.assertIn("Step timeline", html)
        self.assertIn("search", html)


if __name__ == "__main__":
    unittest.main()
