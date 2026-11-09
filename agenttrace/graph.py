"""Iterative parent-forest evidence. Parent does not imply causal precedence."""
from collections import defaultdict,deque

def graph_evidence(steps):
    groups=defaultdict(list)
    for s in steps:groups[s.run_id].append(s)
    result={};issues=[]
    for run,rows in sorted(groups.items()):
        by={s.step:s for s in rows}
        if len(by)!=len(rows):
            issues.append(f"run {run}: duplicate ids prevent graph analysis");result[run]=None;continue
        children={k:[] for k in by};indegree={k:0 for k in by}
        for s in rows:
            if s.parent is not None:
                if s.parent not in by:issues.append(f"run {run}: unknown parent {s.parent!r}")
                else:children[s.parent].append(s.step);indegree[s.step]+=1
        roots=sorted(k for k,n in indegree.items() if n==0);queue=deque(roots);depth={k:1 for k in roots};order=[]
        while queue:
            k=queue.popleft();order.append(k)
            for child in sorted(children[k]):
                indegree[child]-=1;depth[child]=depth[k]+1
                if indegree[child]==0:queue.append(child)
        if len(order)!=len(by):
            issues.append(f"run {run}: cyclic parent graph: {', '.join(sorted(k for k,n in indegree.items() if n))}");result[run]=None
        elif any(s.parent is not None and s.parent not in by for s in rows):result[run]=None
        else:result[run]={'roots':roots,'order':order,'depth':depth,'max_depth':max(depth.values(),default=0)}
    return result,issues
