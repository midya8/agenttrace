import unittest

from agenttrace.parser import parse_lines


VALID = '{"run_id":"r1","step":"a","kind":"llm","name":"planner","duration_ms":10}\n'


class ParserTests(unittest.TestCase):
    def test_valid_minimal_step(self):
        data = parse_lines([VALID])
        self.assertEqual((), data.issues)
        self.assertEqual(1, len(data.steps))
        step = data.steps[0]
        self.assertEqual("r1", step.run_id)
        self.assertEqual("a", step.step)
        self.assertEqual("ok", step.status)
        self.assertEqual(10, step.duration_ms)

    def test_blank_lines_are_ignored(self):
        data = parse_lines(["\n", VALID, "   \n"])
        self.assertEqual(1, len(data.steps))
        self.assertEqual((), data.issues)

    def test_invalid_json_is_reported(self):
        data = parse_lines(['{"run_id":'])
        self.assertEqual(0, len(data.steps))
        self.assertIn("invalid JSON", data.issues[0])

    def test_non_object_is_reported(self):
        data = parse_lines(['[]'])
        self.assertEqual(0, len(data.steps))
        self.assertIn("must be a JSON object", data.issues[0])

    def test_missing_required_fields(self):
        data = parse_lines(['{"run_id":"r1"}'])
        self.assertEqual(0, len(data.steps))
        self.assertIn("step", data.issues[0])
        self.assertIn("kind", data.issues[0])

    def test_duplicate_step_id(self):
        data = parse_lines([VALID, VALID])
        self.assertEqual(2, len(data.steps))
        self.assertTrue(any("duplicate step id" in issue for issue in data.issues))

    def test_unknown_parent(self):
        bad = '{"run_id":"r1","step":"b","parent":"missing","kind":"tool","name":"search"}\n'
        data = parse_lines([bad])
        self.assertTrue(any("unknown parent" in issue for issue in data.issues))

    def test_unknown_kind_and_status(self):
        bad = '{"run_id":"r1","step":"a","kind":"magic","name":"x","status":"weird"}\n'
        data = parse_lines([bad])
        self.assertTrue(any("unknown kind" in issue for issue in data.issues))
        self.assertTrue(any("unknown status" in issue for issue in data.issues))

    def test_negative_numbers_are_rejected(self):
        bad = '{"run_id":"r1","step":"a","kind":"llm","name":"x","duration_ms":-1,"cost_usd":-0.2,"tokens_input":-1}\n'
        data = parse_lines([bad])
        self.assertTrue(any("duration_ms must be non-negative" in issue for issue in data.issues))
        self.assertTrue(any("cost_usd must be non-negative" in issue for issue in data.issues))
        self.assertTrue(any("tokens_input must be non-negative" in issue for issue in data.issues))

    def test_bad_timestamp_is_rejected(self):
        bad = '{"run_id":"r1","step":"a","kind":"llm","name":"x","started_at":"tomorrow"}\n'
        data = parse_lines([bad])
        self.assertTrue(any("ISO-8601" in issue for issue in data.issues))


if __name__ == "__main__":
    unittest.main()
