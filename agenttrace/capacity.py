"""Hypothetical fixed-interval retention with an exact min-cost-flow certificate.

No records are deleted and no real worker capacity/dependencies are inferred.
"""
from copy import deepcopy
import re


def normalize(request):
    if not isinstance(request,dict) or set(request)!={'capacity','intervals'}:
        raise ValueError('exact capacity and intervals fields required')
    r=deepcopy(request)
    if type(r['capacity'])is not int or not 0<=r['capacity']<=4:
        raise ValueError('capacity needs integer 0..4')
    rows=r['intervals']
    if not isinstance(rows,list) or len(rows)>12:raise ValueError('at most twelve explicit intervals')
    ids=set()
    for t in rows:
        if not isinstance(t,dict)or set(t)!={'id','start','end','drop_penalty'}:raise ValueError('exact interval fields id/start/end/drop_penalty')
        if not isinstance(t['id'],str)or re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,23}',t['id'],flags=re.ASCII)is None:raise ValueError('bounded ASCII id required')
        if t['id']in ids:raise ValueError('duplicate interval id')
        ids.add(t['id'])
        for k,limit in [('start',1000000),('end',1000000),('drop_penalty',1000)]:
            if type(t[k])is not int or not 0<=t[k]<=limit:raise ValueError('bounded nonnegative integer '+k+' required')
        if t['end']<t['start']:raise ValueError('interval end precedes start')
    return r


def _residual(edges):
    result=[]
    for i,e in enumerate(edges):
        if e['flow']<e['capacity']:result.append({'edge':i,'direction':1,'from':e['from'],'to':e['to'],'capacity':e['capacity']-e['flow'],'cost':e['cost']})
        if e['flow']:result.append({'edge':i,'direction':-1,'from':e['to'],'to':e['from'],'capacity':e['flow'],'cost':-e['cost']})
    return result


def _distances(n,arcs,source=None):
    distance=[0]*n if source is None else [None]*n
    if source is not None:distance[source]=0
    pred=[None]*n
    for _ in range(max(0,n-1)):
        changed=False
        for a in arcs:
            u,v=a['from'],a['to']
            if distance[u]is not None and (distance[v]is None or distance[v]>distance[u]+a['cost']):
                distance[v]=distance[u]+a['cost'];pred[v]=a;changed=True
        if not changed:break
    for a in arcs:
        if distance[a['from']]is not None and (distance[a['to']]is None or distance[a['to']]>distance[a['from']]+a['cost']):raise ArithmeticError('negative residual cycle')
    return distance,pred


def _solve(rows,k):
    n=len(rows);scale=1<<n
    times=sorted({x for t in rows if t['start']<t['end']for x in [t['start'],t['end']]})
    vertices={v:i for i,v in enumerate(times)}
    edges=[{'kind':'idle','id':'gap_'+str(i),'from':i,'to':i+1,'capacity':k,'cost':0,'flow':0}for i in range(max(0,len(times)-1))]
    for i,t in enumerate(rows):
        if t['start']<t['end']:edges.append({'kind':'interval','id':t['id'],'from':vertices[t['start']],'to':vertices[t['end']],'capacity':1,'cost':-(t['drop_penalty']*scale-(1<<i)),'flow':0})
    if times:
        for _ in range(k):
            _,pred=_distances(len(times),_residual(edges),0)
            v=len(times)-1
            while v:
                a=pred[v]
                if a is None:raise ArithmeticError('missing idle path')
                edges[a['edge']]['flow']+=a['direction'];v=a['from']
    selected={e['id']for e in edges if e['kind']=='interval'and e['flow']}
    selected.update(t['id']for t in rows if t['start']==t['end']and t['drop_penalty']>0)
    mask=sum(1<<i for i,t in enumerate(rows)if t['id']in selected)
    retained=sum(t['drop_penalty']for t in rows if t['id']in selected)
    arcs=_residual(edges);potential,_=_distances(len(times),arcs)
    for a in arcs:a['reduced_cost']=a['cost']+potential[a['from']]-potential[a['to']]
    objective=sum(e['flow']*e['cost']for e in edges)
    dual=k*(potential[-1]-potential[0])if times else 0
    dual+=sum(e['capacity']*min(0,e['cost']+potential[e['from']]-potential[e['to']])for e in edges)
    if objective!=dual or any(a['reduced_cost']<0 for a in arcs):raise ArithmeticError('invalid optimum certificate')
    return {'capacity':k,'retained_mask':mask,'retained_ids':[t['id']for t in rows if t['id']in selected],
            'dropped_ids':[t['id']for t in rows if t['id']not in selected],'retained_penalty':retained,
            'drop_penalty':sum(t['drop_penalty']for t in rows)-retained,
            'network':{'times':times,'edges':edges,'potentials':potential,'residual':arcs,
                       'flow_value':k if times else 0,'cost':objective,'dual_bound':dual,'gap':objective-dual}}


def capacity_report(request):
    r=normalize(request);rows=r['intervals'];k=r['capacity'];solutions=[_solve(rows,c)for c in range(5)];chosen=solutions[k]
    selected=set(chosen['retained_ids']);boundaries=sorted({x for t in rows for x in [t['start'],t['end']]})
    segments=[]
    for left,right in zip(boundaries,boundaries[1:]):
        original=[t['id']for t in rows if t['start']<=left<t['end']]
        retained=[s for s in original if s in selected]
        segments.append({'start':left,'end':right,'original_active':original,'retained_active':retained,
                         'original_count':len(original),'retained_count':len(retained),'within_capacity':len(retained)<=k})
    lane_ends=[-1]*k;lane_for={}
    for i in sorted(range(len(rows)),key=lambda i:(rows[i]['start'],rows[i]['end'],i)):
        t=rows[i]
        if t['id']in selected and t['start']<t['end']:
            lane=next(j for j,end in enumerate(lane_ends)if end<=t['start']);lane_ends[lane]=t['end'];lane_for[t['id']]=lane
    return {'schema':1,'input':r,'tie_scale':1<<len(rows),'selected':chosen,
            'frontier':[{key:v for key,v in s.items()if key!='network'}for s in solutions],
            'intervals':[{**t,'retained':t['id']in selected,'point':t['start']==t['end'],
                          'lane':lane_for.get(t['id'])}for t in rows], 'segments':segments,
            'original_peak':max((s['original_count']for s in segments),default=0),
            'retained_peak':max((s['retained_count']for s in segments),default=0),
            'limits':'Hypothetical supplied half-open intervals and drop penalties, not trace deletion, inferred resource use, dependency repair, counterfactual runtime or production scheduling. Unknown timing cannot be certified; original trace analyzer and gates unchanged.'}
