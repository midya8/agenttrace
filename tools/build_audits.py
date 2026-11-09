"""Retain complete synthetic graph/timing evidence, never a model benchmark."""
import json,sys,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from agenttrace.audit import audit_trace
BASE=datetime.datetime(2026,11,7,tzinfo=datetime.timezone.utc)
def row(k,t=0,d=10,parent=None,run='r',**kw):
    r=dict(run_id=run,step=k,parent=parent,kind='tool',name='fixture',duration_ms=d,**kw)
    if t is not None:r['started_at']=(BASE+datetime.timedelta(milliseconds=t)).isoformat(timespec='milliseconds').replace('+00:00','Z')
    return r

def build():
    cases=[]
    def add(name,events):cases.append(dict(name=name,report=audit_trace(dict(events=events))))
    original=[json.loads(s) for s in (ROOT/'examples/trace.jsonl').read_text().splitlines()]
    add('Original fixed five-step trace',original)
    add('Nested time is counted more than once',[row('parent',0,100),row('a',10,60,'parent'),row('b',30,50,'parent')])
    add('Adjacent half-open intervals',[row('a',0,20),row('b',20,20,'a')])
    add('Gaps remain uncovered',[row('a',0,10),row('b',100,10,'a')])
    add('Zero-duration events are points',[row('before',0,0),row('a',20,10),row('inside',25,0),row('after',100,0)])
    add('Missing timestamp is not time zero',[row('a',None,90),row('b',20,10,'a')])
    add('All timestamps missing',[row('a',None,30),row('b',None,40,'a')])
    add('Out-of-order parent references',[row('c',50,10,'b'),row('b',20,20,'a'),row('a',0,10)])
    add('Child before parent is a relation, not corruption',[row('parent',50,10),row('child',0,20,'parent')])
    add('Child outlives parent',[row('parent',0,10),row('child',5,50,'parent')])
    add('Multiple roots',[row('a',0,10),row('b',5,10),row('c',7,1,'a')])
    add('Four independent runs',[row('a',i*10,20,run=str(i)) for i in range(4)])
    add('One event',[row('a',0,100)])
    add('Only points',[row('a',0,0),row('b',20,0,'a')])
    add('Empty trace',[])
    add('Failure status is not a timing explanation',[row('a',0,10,status='timeout'),dict(row('b',10,20),kind='error')])
    add('Payload remains data',[row('__proto__',0,20,input={'constructor':'<img src=x onerror=alert(1)>'},output={'text':'<script>throw 1</script>'}),row('constructor',5,20,'__proto__')])
    add('Sixteen concurrent records',[row(str(i),0,100) for i in range(16)])
    add('Sixteen-deep parent chain',[row(str(i),i*20,10,str(i-1) if i else None) for i in range(16)])
    add('P95 interpolates, not nearest rank',[row('a',0,10),row('b',0,20)])
    add('P95 ties',[row('a',0,10),row('b',20,10),row('c',40,10)])
    add('Same endpoints and zero point',[row('a',0,20),row('b',0,20),row('c',20,20),row('point',20,0)])
    add('Known zero plus unknown duration',[row('known',100,0),row('unknown',None,70)])
    add('Costs and tokens are supplied fixture values',[row('a',0,10,cost_usd=.0018,tokens_input=420,tokens_output=180)])
    return {'schema_version':1,'cases':cases}
if __name__=='__main__':
    data=build();(ROOT/'docs/audit.json').write_text(json.dumps(data,separators=(',',':'),sort_keys=True,allow_nan=False)+'\n');(ROOT/'examples/audit.json').write_text(json.dumps({'events':[row('parent',0,100),row('a',10,60,'parent'),row('b',30,50,'parent')]},indent=2,sort_keys=True)+'\n');print('Retained',len(data['cases']),'complete reports')
