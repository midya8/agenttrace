"""Complete interval coverage witnesses; never inferred CPU or causal time."""
from collections import defaultdict

def timing_evidence(rows):
    """Rows have step, start_ms (or None) and duration_ms. Half-open intervals."""
    timed=[r for r in rows if r['start_ms'] is not None];unknown=sorted(r['step'] for r in rows if r['start_ms'] is None)
    boundaries=defaultdict(lambda:{'starts':[],'ends':[],'points':[]})
    for r in timed:
        a=r['start_ms'];b=a+r['duration_ms']
        if a==b:boundaries[a]['points'].append(r['step'])
        else:boundaries[a]['starts'].append(r['step']);boundaries[b]['ends'].append(r['step'])
    active=set();points=sorted(boundaries);events=[];segments=[]
    for i,x in enumerate(points):
        e=boundaries[x];ends=sorted(e['ends']);starts=sorted(e['starts']);zero=sorted(e['points'])
        active.difference_update(ends);active.update(starts)
        events.append({'at_ms':x,'ends':ends,'starts':starts,'points':zero,'active_after':sorted(active)})
        if i+1<len(points):
            y=points[i+1];d=y-x;segments.append({'start_ms':x,'end_ms':y,'width_ms':d,'active_ids':sorted(active),'count':len(active),'covered_ms':d if active else 0,'weighted_ms':d*len(active)})
    span=points[-1]-points[0] if points else None;busy=sum(s['covered_ms'] for s in segments);weighted=sum(s['weighted_ms'] for s in segments)
    return {'complete':not unknown,'timed_ids':sorted(r['step'] for r in timed),'unknown_ids':unknown,
            'events':events,'segments':segments,'recorded_span_ms':span,'busy_union_ms':busy if timed else None,
            'uncovered_ms':span-busy if span is not None else None,'timed_duration_sum_ms':sum(r['duration_ms'] for r in timed),
            'step_duration_sum_ms':sum(r['duration_ms'] for r in rows),'weighted_area_ms':weighted,
            'overlap_excess_ms':weighted-busy if timed else None,'peak_recorded_spans':max((s['count'] for s in segments),default=0)}
