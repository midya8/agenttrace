"""Bounded full-record graph/timing inspector for supplied synthetic traces."""
import copy,json,math,re
from dataclasses import asdict
from datetime import datetime,timezone
from pathlib import Path
from .parser import parse_lines
from .graph import graph_evidence
from .timing import timing_evidence

FIELDS={'run_id','step','parent','kind','name','status','started_at','duration_ms','tokens_input','tokens_output','cost_usd','input','output'}
def _text(v,n=64):
    if not isinstance(v,str) or len(v)>n or any(ord(c)>126 or (ord(c)<32 and c not in '\t\r\n') for c in v):raise ValueError('Audit text must be bounded ASCII')
def _payload(v,depth=0):
    if depth>4:raise ValueError('Audit payload nesting exceeds four')
    if v is None or isinstance(v,bool):return
    if isinstance(v,str):_text(v,512);return
    if isinstance(v,int) and abs(v)<=1000000:return
    if isinstance(v,(dict,list)) and len(v)<=16:
        for k,x in (v.items() if isinstance(v,dict) else enumerate(v)):
            if isinstance(v,dict):_text(k)
            _payload(x,depth+1)
        return
    raise ValueError('Audit payload supports bounded integer/text/Boolean/null JSON')
def _number(v,maximum,scale=1):
    if isinstance(v,bool) or not isinstance(v,(float,int)) or not 0<=v<=maximum or not math.isfinite(v) or (v!=round(v) if scale==1 else abs(v*scale-round(v*scale))>1e-8):raise ValueError('Audit numeric bound/grid violation')
def audit_trace(spec):
    if not isinstance(spec,dict) or set(spec)!={'events'} or not isinstance(spec['events'],list) or len(spec['events'])>16:raise ValueError('Audit needs events list, at most 16 records')
    source=copy.deepcopy(spec['events'])
    for r in source:
        if not isinstance(r,dict) or set(r)-FIELDS:raise ValueError('Unknown audit event field')
        for k in ['run_id','step','name']:_text(r.get(k))
        if r.get('parent') is not None:_text(r['parent'])
        _number(r.get('duration_ms',0),1000000);_number(r.get('cost_usd',0),1,1000000)
        for k in ['tokens_input','tokens_output']:
            v=r.get(k,0)
            if isinstance(v,bool) or not isinstance(v,int) or not 0<=v<=1000000:raise ValueError('Audit token bound')
        for k in ['input','output']:_payload(r.get(k))
        t=r.get('started_at')
        if t is not None:
            if not isinstance(t,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z',t):raise ValueError('Audit timestamps require UTC seconds or three-digit milliseconds')
            try:dt=datetime.fromisoformat(t.replace('Z','+00:00'))
            except ValueError as exc:raise ValueError('Invalid audit date') from exc
            if not 2000<=dt.year<=2100:raise ValueError('Audit date bound 2000..2100')
    data=parse_lines(json.dumps(r,allow_nan=False) for r in source)
    if data.issues:raise ValueError('; '.join(data.issues))
    graphs,_=graph_evidence(data.steps)
    if len(graphs)>4:raise ValueError('Audit supports at most four runs')
    records=[]
    for s in data.steps:
        r=asdict(s);dt=s.started
        diff=dt-datetime(1970,1,1,tzinfo=timezone.utc) if dt else None
        r['start_ms']=(diff.days*86400000+diff.seconds*1000+diff.microseconds//1000) if diff is not None else None
        records.append(r)
    runs=[]
    for run,g in sorted(graphs.items()):
        rows=[r for r in records if r['run_id']==run];by={r['step']:r for r in rows};paths=[];edges=[]
        for r in sorted(rows,key=lambda r:r['step']):
            ids=[];k=r['step']
            while k is not None:ids.insert(0,k);k=by[k]['parent']
            paths.append({'step':r['step'],'ids':ids,'depth':len(ids),'parent_path_duration_sum_ms':sum(by[k]['duration_ms'] for k in ids)})
            if r['parent'] is not None:
                p=by[r['parent']];known=r['start_ms'] is not None and p['start_ms'] is not None
                edges.append({'parent':p['step'],'child':r['step'],'both_timed':known,
                              'child_starts_before_parent':r['start_ms']<p['start_ms'] if known else None,
                              'child_ends_after_parent':r['start_ms']+r['duration_ms']>p['start_ms']+p['duration_ms'] if known else None})
        ordered=sorted(rows,key=lambda r:(r['duration_ms'],r['step']));rank=(len(rows)-1)*.95;lo=int(rank);hi=min(lo+1,len(rows)-1);w=rank-lo
        p95={'ordered':[{'step':r['step'],'duration_ms':r['duration_ms']} for r in ordered], 'rank':rank,'low_index':lo,'high_index':hi,'high_weight':w,'low_value':ordered[lo]['duration_ms'],'high_value':ordered[hi]['duration_ms'],'value_ms':ordered[lo]['duration_ms']*(1-w)+ordered[hi]['duration_ms']*w}
        runs.append({'run_id':run,'graph':g,'paths':paths,'parent_time_relations':edges,'timing':timing_evidence(rows),'p95':p95,
                     'errors':[r['step'] for r in rows if r['kind']=='error' or r['status']!='ok']})
    return {'schema_version':1,'spec':{'events':source},'records':records,'runs':runs}
def load_spec(path):
    if Path(path).stat().st_size>131072:raise ValueError('Audit spec exceeds 128KiB')
    def unique(items):
        d={}
        for k,v in items:
            if k in d:raise ValueError('Duplicate JSON key')
            d[k]=v
        return d
    return json.loads(Path(path).read_text(),object_pairs_hook=unique,parse_constant=lambda v:(_ for _ in ()).throw(ValueError('Nonfinite JSON token')))
