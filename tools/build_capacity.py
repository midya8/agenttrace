"""Deterministic synthetic capacity controls; browser bundle contains inputs only."""
import json
from pathlib import Path
import random
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agenttrace.capacity import capacity_report
ROOT=Path(__file__).resolve().parents[1]
def make(tuples,k=1):return {'capacity':k,'intervals':[{'id':'span_'+str(i),'start':a,'end':b,'drop_penalty':w}for i,(a,b,w)in enumerate(tuples)]}
cases=[{'id':'one-long-vs-two-touching','input':make([(0,4,9),(0,2,6),(2,4,6)])},
 {'id':'two-lanes','input':make([(0,4,9),(0,2,6),(2,4,6)],2)},
 {'id':'zero-capacity','input':make([(0,4,9),(0,2,6),(2,4,6)],0)},
 {'id':'point-is-an-empty-interval','input':make([(0,4,9),(2,2,7),(4,4,0)],0)},
 {'id':'touching-not-overlapping','input':make([(0,2,5),(2,4,5),(4,6,5)])},
 {'id':'identical-intervals-tie-order','input':make([(0,4,5)]*4)},
 {'id':'reversed-input-tie-labels','input':{'capacity':1,'intervals':[{'id':'last','start':0,'end':4,'drop_penalty':5},{'id':'first','start':0,'end':4,'drop_penalty':5}]}},
 {'id':'zero-penalty','input':make([(0,2,0),(2,4,0),(2,2,0)])},
 {'id':'empty','input':make([])},
 {'id':'nested-spans','input':make([(0,8,12),(1,7,10),(2,6,8),(3,5,6)],2)},
 {'id':'all-fit','input':make([(0,8,12),(1,7,10),(2,6,8),(3,5,6)],4)},
 {'id':'max-bounds','input':make([(i*20000,1000000-i*20000,1000-i*20)for i in range(12)],4)}]
rng=random.Random(991)
for j in range(12):
 tuples=[]
 for i in range(rng.randint(2,9)):
  a,b=sorted([rng.randrange(12),rng.randrange(12)]);tuples.append((a,b,rng.randrange(20)))
 cases.append({'id':'seeded_'+str(j),'input':make(tuples,rng.randrange(5))})
reports=[{'id':c['id'],'report':capacity_report(c['input'])}for c in cases]
(ROOT/'examples/capacity.json').write_text(json.dumps(cases[0]['input'],indent=2)+'\n')
(ROOT/'examples/capacity-reports.json').write_text(json.dumps(reports,separators=(',',':'))+'\n')
(ROOT/'docs/capacity-data.js').write_text('window.CapacityInputs='+json.dumps(cases,separators=(',',':'))+';\n')
print(json.dumps({'reports':len(reports),'intervals':sum(len(c['report']['intervals'])for c in reports),'segments':sum(len(c['report']['segments'])for c in reports),'edges':sum(len(c['report']['selected']['network']['edges'])for c in reports),'residual':sum(len(c['report']['selected']['network']['residual'])for c in reports)}))
