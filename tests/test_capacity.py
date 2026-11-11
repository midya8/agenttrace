"""Independent unit-cell, full-subset and LP certificate checks."""
import copy
import itertools
import random
import unittest
from agenttrace.capacity import capacity_report


def oracle(rows,k):
    candidates=[]
    for bits in itertools.product([0,1],repeat=len(rows)):
        # Unit cells are a separate reference for bounded integer endpoints.
        peak=max((sum(bit and t['start']<=cell<t['end']for bit,t in zip(bits,rows))for cell in range(max((t['end']for t in rows),default=0))),default=0)
        if peak<=k:
            penalty=sum(t['drop_penalty']for bit,t in zip(bits,rows)if bit)
            mask=sum(bit*(1<<i)for i,bit in enumerate(bits))
            candidates.append((-penalty,mask))
    return min(candidates)


class CapacityTests(unittest.TestCase):
    def test_weighted_greedy_counterexample(self):
        rows=[dict(id='long',start=0,end=4,drop_penalty=9),dict(id='left',start=0,end=2,drop_penalty=6),dict(id='right',start=2,end=4,drop_penalty=6)]
        r=capacity_report(dict(capacity=1,intervals=rows));s=r['selected']
        self.assertEqual(s['retained_ids'],['left','right']);self.assertEqual(s['drop_penalty'],9)
        self.assertEqual([s['drop_penalty']for s in r['frontier']],[21,9,0,0,0])
        self.assertEqual([t['lane']for t in r['intervals']],[None,0,0])

    def test_250_seeded_all_capacities_against_full_subsets(self):
        rng=random.Random(43)
        for case in range(250):
            n=rng.randrange(10);rows=[]
            for i in range(n):
                a,b=sorted([rng.randrange(8),rng.randrange(8)])
                rows.append(dict(id='t'+str(i),start=a,end=b,drop_penalty=rng.randrange(12)))
            r=capacity_report(dict(capacity=rng.randrange(5),intervals=rows))
            for k,s in enumerate(r['frontier']):
                self.assertEqual((-s['retained_penalty'],s['retained_mask']),oracle(rows,k))
            self.assertTrue(all(a['drop_penalty']>=b['drop_penalty']for a,b in zip(r['frontier'],r['frontier'][1:])))

    def test_primal_dual_and_lane_certificates(self):
        rng=random.Random(701)
        for _ in range(120):
            rows=[]
            for i in range(rng.randrange(13)):
                a,b=sorted([rng.randrange(1000001),rng.randrange(1000001)])
                rows.append(dict(id='t'+str(i),start=a,end=b,drop_penalty=rng.randrange(1001)))
            k=rng.randrange(5);r=capacity_report(dict(capacity=k,intervals=rows));s=r['selected'];net=s['network'];edges=net['edges'];times=net['times'];p=net['potentials']
            balances=[0]*len(times)
            for e in edges:
                self.assertGreaterEqual(e['flow'],0);self.assertLessEqual(e['flow'],e['capacity'])
                balances[e['from']]+=e['flow'];balances[e['to']]-=e['flow']
                reduced=e['cost']+p[e['from']]-p[e['to']]
                if e['flow']<e['capacity']:self.assertGreaterEqual(reduced,0)
                if e['flow']>0:self.assertLessEqual(reduced,0)
            if times:self.assertEqual(balances,[k]+[0]*(len(times)-2)+[-k])
            self.assertEqual(net['cost'],sum(e['flow']*e['cost']for e in edges))
            self.assertEqual(net['cost'],net['dual_bound']);self.assertEqual(net['gap'],0)
            self.assertTrue(all(a['reduced_cost']>=0 for a in net['residual']))
            for lane in range(k):
                selected=sorted([t for t in r['intervals']if t['lane']==lane],key=lambda t:t['start'])
                self.assertTrue(all(a['end']<=b['start']for a,b in zip(selected,selected[1:])))
            self.assertTrue(all(s['within_capacity']for s in r['segments']))

    def test_points_zero_penalties_and_canonical_ties(self):
        rows=[dict(id='a',start=0,end=1,drop_penalty=1),dict(id='b',start=0,end=1,drop_penalty=1),dict(id='point',start=1,end=1,drop_penalty=1),dict(id='free',start=0,end=0,drop_penalty=0)]
        r=capacity_report(dict(capacity=1,intervals=rows));self.assertEqual(r['selected']['retained_ids'],['a','point'])
        self.assertIsNone(r['intervals'][2]['lane']);self.assertFalse(r['intervals'][3]['retained'])
        r=capacity_report(dict(capacity=0,intervals=rows));self.assertEqual(r['selected']['retained_ids'],['point'])
        for k in range(5):
            r=capacity_report(dict(capacity=k,intervals=[]));self.assertEqual(r['selected']['drop_penalty'],0);self.assertEqual(r['selected']['network']['cost'],0)

    def test_strict_contract_and_input_purity(self):
        x=dict(capacity=1,intervals=[dict(id='a',start=0,end=2,drop_penalty=7)]);before=copy.deepcopy(x);capacity_report(x);self.assertEqual(x,before)
        for value in [True,-1,5,1.0,None]:
            with self.assertRaises(ValueError):capacity_report({**x,'capacity':value})
        for key,value in [('start',None),('start',True),('start',-1),('end',1000001),('end',-1),('drop_penalty',1001),('id','<x>')]:
            y=copy.deepcopy(x);y['intervals'][0][key]=value
            with self.assertRaises(ValueError):capacity_report(y)
        for y in [{**x,'unknown':1},{**x,'intervals':x['intervals']*2},{**x,'intervals':{}},{**x,'intervals':[{}]}]:
            with self.assertRaises(ValueError):capacity_report(y)

    def test_saved_reports_regenerate_exactly(self):
        import json
        from pathlib import Path
        for c in json.loads((Path(__file__).resolve().parents[1]/'examples/capacity-reports.json').read_text()):self.assertEqual(capacity_report(c['report']['input']),c['report'])

    def test_strict_json_and_cli(self):
        import json,subprocess,sys
        from agenttrace.capacity_cli import loads
        for text in ['{"x":1,"x":2}','1e0','-0','NaN','2.0','['*10+'0'+']'*10,' '*131073]:
            with self.assertRaises(ValueError):loads(text)
        x={'capacity':1,'intervals':[{'id':'x','start':0,'end':2,'drop_penalty':8}]}
        for text in [json.dumps(x),'{"capacity":true,"intervals":[]}','{"x":1,"x":2}']:
            p=subprocess.run([sys.executable,'-m','agenttrace.capacity_cli','--input','-'],input=text,text=True,capture_output=True)
            if text==json.dumps(x):self.assertEqual(p.returncode,0);self.assertEqual(json.loads(p.stdout),capacity_report(x))
            else:self.assertEqual(p.returncode,2);self.assertEqual(p.stdout,'');self.assertIn('capacity error',p.stderr)
