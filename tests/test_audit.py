import contextlib,copy,hashlib,io,itertools,json,math,tempfile,unittest
from pathlib import Path
from agenttrace.audit import audit_trace,load_spec
from agenttrace.timing import timing_evidence
from agenttrace.graph import graph_evidence
from agenttrace.parser import parse_lines
from agenttrace.analysis import analyze_steps
from agenttrace.compare import compare_results
from agenttrace.cli import main
ROOT=Path(__file__).resolve().parents[1]
def r(k='a',**kw):return dict(run_id='r',step=k,kind='tool',name='x',**kw)
def parsed(rows):return parse_lines(json.dumps(x) for x in rows)
class AuditTests(unittest.TestCase):
 def test_retained_full_reports(self):
  f=json.loads((ROOT/'docs/audit.json').read_text());self.assertEqual(len(f['cases']),24)
  for c in f['cases']:self.assertEqual(audit_trace(c['report']['spec']),c['report'])
 def test_original_files_unchanged(self):
  for p,h in json.loads((ROOT/'docs/original-sha256.json').read_text()).items():self.assertEqual(hashlib.sha256((ROOT/('docs/original-readme.md' if p=='README.md' else p)).read_bytes()).hexdigest(),h,p)
 def test_all_small_interval_lists_against_unit_cells(self):
  choices=[(a,b) for a in range(4) for b in range(a,4)];checked=0
  for n in range(1,5):
   for xs in itertools.product(choices,repeat=n):
    rows=[dict(step=str(i),start_ms=a,duration_ms=b-a) for i,(a,b) in enumerate(xs)];v=timing_evidence(rows);counts=[sum(a<=x<b for a,b in xs) for x in range(3)];self.assertEqual(v['busy_union_ms'],sum(c>0 for c in counts));self.assertEqual(v['peak_recorded_spans'],max(counts));self.assertEqual(v['weighted_area_ms'],sum(b-a for a,b in xs));self.assertEqual(v['recorded_span_ms'],max(b for a,b in xs)-min(a for a,b in xs));checked+=1
  self.assertEqual(checked,11110)
 def test_missing_not_zero(self):
  v=timing_evidence([dict(step='a',start_ms=None,duration_ms=100),dict(step='b',start_ms=20,duration_ms=0)]);self.assertFalse(v['complete']);self.assertEqual(v['busy_union_ms'],0);self.assertEqual(v['timed_duration_sum_ms'],0);self.assertEqual(v['step_duration_sum_ms'],100)
 def test_empty_timing_undefined(self):self.assertIsNone(timing_evidence([])['recorded_span_ms'])
 def test_nested_not_elapsed(self):
  v=audit_trace(json.loads((ROOT/'examples/audit.json').read_text()))['runs'][0];self.assertEqual(v['timing']['step_duration_sum_ms'],210);self.assertEqual(v['timing']['busy_union_ms'],100);self.assertEqual(v['timing']['peak_recorded_spans'],3)
 def test_half_open_boundary(self):
  v=timing_evidence([dict(step='a',start_ms=0,duration_ms=10),dict(step='b',start_ms=10,duration_ms=10)]);self.assertEqual(v['peak_recorded_spans'],1);self.assertEqual(v['events'][1]['ends'],['a']);self.assertEqual(v['events'][1]['active_after'],['b'])
 def test_p95_witness(self):
  v=audit_trace({'events':[r(duration_ms=10),r('b',duration_ms=20)]})['runs'][0]['p95'];self.assertEqual(v['value_ms'],19.5);self.assertEqual(v['rank'],.95)
 def test_cycle_rejected(self):
  d=parsed([r(parent='b'),r('b',parent='a')]);self.assertTrue(any('cyclic' in x for x in d.issues));self.assertFalse(analyze_steps(d.steps,d.issues).ok)
 def test_self_parent_rejected(self):self.assertTrue(parsed([r(parent='a')]).issues)
 def test_forward_parent_is_valid(self):
  d=parsed([r('b',parent='a'),r()]);self.assertEqual(d.issues,());self.assertEqual(analyze_steps(d.steps).runs[0].max_depth,2)
 def test_deep_chain_no_recursion(self):
  d=parsed([r(str(i),parent=str(i-1) if i else None) for i in range(5000)]);self.assertFalse(d.issues);self.assertEqual(analyze_steps(d.steps).runs[0].max_depth,5000)
 def test_mixed_timestamp_sort(self):
  d=parsed([r(),r('b',started_at='2026-11-07T00:00:00Z')]);self.assertTrue(analyze_steps(d.steps).ok)
 def test_parser_nonfinite_and_duplicate_json(self):
  for text in ['{"run_id":"r","step":"a","kind":"tool","name":"x","cost_usd":NaN}','{"run_id":"r","run_id":"s"}']:
   self.assertTrue(parse_lines([text]).issues)
 def test_overflow_number_is_issue(self):self.assertTrue(parsed([r(duration_ms=10**1000)]).issues)
 def test_whitespace_id_and_empty_parent_rejected(self):
  for row in [r(' '),r(parent='')]:self.assertTrue(parsed([row]).issues)
 def test_original_source_line_number(self):
  d=parse_lines(['','{}',json.dumps(r(parent='missing'))]);self.assertTrue(any('line 3: unknown' in x for x in d.issues))
 def test_analysis_json_ok_false_on_invalid(self):
  d=parsed([r(parent='missing')]);self.assertFalse(analyze_steps(d.steps,d.issues).to_dict()['ok'])
 def test_compare_invalid_not_pass(self):
  d=parsed([r(parent='missing')]);a=analyze_steps(d.steps,d.issues);self.assertFalse(compare_results(a,a).ok)
 def test_zero_baseline_pct_undefined(self):
  a=analyze_steps([]);b=analyze_steps(parsed([r()]).steps);c=compare_results(a,b);self.assertIsNone(next(v for v in c.deltas if v.metric=='steps').delta_pct);self.assertFalse(compare_results(a,b,max_step_increase_pct=0).ok)
 def test_nonfinite_gates_rejected(self):
  with self.assertRaises(ValueError):analyze_steps([],max_cost_usd=float('nan'))
  with self.assertRaises(ValueError):compare_results(analyze_steps([]),analyze_steps([]),max_new_errors=True)
 def test_bounded_invalids(self):
  for x in [{'events':[r(duration_ms=1+1e-10)]},{'events':[r(duration_ms=.5)]},{'events':[r(status=None)]},{'events':[r(started_at='2026-02-30T00:00:00Z')]},{'events':[r(input={'x':.5})]},{'events':[r(extra=1)]},{'events':[r(parent='a')]}]:
   with self.assertRaises(ValueError):audit_trace(x)
 def test_loader_strict(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x'
   for s in ['{"events":[],"events":[]}','{"events":NaN}',' '*131073]:
    p.write_text(s)
    with self.assertRaises(ValueError):load_spec(p)
 def test_cli_export(self):
  with tempfile.TemporaryDirectory() as d,contextlib.redirect_stdout(io.StringIO()):
   p=Path(d)/'out';self.assertEqual(main(['audit','--spec',str(ROOT/'examples/audit.json'),'--json',str(p)]),0);self.assertEqual(json.loads(p.read_text()),audit_trace(json.loads((ROOT/'examples/audit.json').read_text())))
