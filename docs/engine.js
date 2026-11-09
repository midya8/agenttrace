/* Independent scalar graph and interval sweep. Parent links are not dependencies. */
const fields=new Set(['run_id','step','parent','kind','name','status','started_at','duration_ms','tokens_input','tokens_output','cost_usd','input','output']);
const text=(v,n=64)=>{if(typeof v!=='string'||v.length>n||/[^\x20-\x7e\t\r\n]/.test(v))throw Error('Audit text must be bounded ASCII')};
const number=(v,max,scale=1)=>{if(typeof v!=='number'||!Number.isFinite(v)||v<0||v>max||(scale===1?!Number.isInteger(v):Math.abs(v*scale-Math.round(v*scale))>1e-8))throw Error('Audit numeric bound/grid violation')};
function payload(v,depth=0){if(depth>4)throw Error('Payload nesting exceeds four');if(v===null||typeof v==='boolean')return;if(typeof v==='string'){text(v,512);return}if(Number.isInteger(v)&&Math.abs(v)<=1000000)return;if(v&&typeof v==='object'&&Object.keys(v).length<=16){for(const [k,x] of Object.entries(v)){if(!Array.isArray(v))text(k);payload(x,depth+1)}return}throw Error('Unsupported bounded payload')}
export function auditTrace(spec){
 if(!spec||typeof spec!=='object'||Array.isArray(spec)||Object.keys(spec).length!==1||!Array.isArray(spec.events)||spec.events.length>16)throw Error('Audit needs events list, at most 16');
 const source=structuredClone(spec.events),records=[],groups=new Map();
 for(const [sequence,r] of source.entries()){
  if(!r||typeof r!=='object'||Array.isArray(r)||Object.keys(r).some(k=>!fields.has(k)))throw Error('Unknown event field');
  for(const k of ['run_id','step','name']){text(r[k]);if(!r[k].trim())throw Error('Empty id/name')}
  const parent=r.parent??null;if(parent!==null){text(parent);if(!parent.trim())throw Error('Empty parent')}
  if(!['llm','tool','action','observation','error'].includes(r.kind)||!['ok','failed','cancelled','timeout'].includes(r.status===undefined?'ok':r.status))throw Error('Invalid kind/status');
  const d=r.duration_ms===undefined?0:r.duration_ms,cost=r.cost_usd===undefined?0:r.cost_usd;number(d,1000000);number(cost,1,1000000);
  for(const k of ['tokens_input','tokens_output']){const v=r[k]===undefined?0:r[k];if(typeof v!=='number'||!Number.isInteger(v)||v<0||v>1000000)throw Error('Token bound')}
  for(const k of ['input','output'])payload(r[k]??null);
  const t=r.started_at??null;let start=null;
  if(t!==null){if(typeof t!=='string'||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/.test(t))throw Error('UTC timestamp format');start=Date.parse(t);const expected=t.includes('.')?t:t.replace('Z','.000Z');if(!Number.isFinite(start)||new Date(start).toISOString()!==expected||Number(t.slice(0,4))<2000||Number(t.slice(0,4))>2100)throw Error('Invalid date')}
  const row={run_id:r.run_id,step:r.step,parent,kind:r.kind,name:r.name,status:r.status===undefined?'ok':r.status,started_at:t,duration_ms:d,tokens_input:r.tokens_input??0,tokens_output:r.tokens_output??0,cost_usd:cost,input:r.input??null,output:r.output??null,sequence,start_ms:start};
  records.push(row);if(!groups.has(row.run_id))groups.set(row.run_id,[]);groups.get(row.run_id).push(row)
 }
 if(groups.size>4)throw Error('At most four runs');const runs=[];
 for(const run of [...groups.keys()].sort()){
  const rows=groups.get(run),by=new Map(rows.map(r=>[r.step,r]));if(by.size!==rows.length)throw Error('Duplicate step ids');
  const children=new Map(rows.map(r=>[r.step,[]])),degree=new Map(rows.map(r=>[r.step,0]));
  for(const r of rows)if(r.parent!==null){if(!by.has(r.parent))throw Error('Unknown parent');children.get(r.parent).push(r.step);degree.set(r.step,1)}
  const roots=rows.filter(r=>degree.get(r.step)===0).map(r=>r.step).sort(),queue=[...roots],depth=new Map(roots.map(k=>[k,1])),order=[];
  while(queue.length){const k=queue.shift();order.push(k);for(const child of children.get(k).sort()){degree.set(child,degree.get(child)-1);depth.set(child,depth.get(k)+1);if(degree.get(child)===0)queue.push(child)}}
  if(order.length!==rows.length)throw Error('Cyclic parent graph');
  const paths=[],edges=[];
  for(const r of [...rows].sort((a,b)=>a.step<b.step?-1:a.step>b.step?1:0)){const ids=[];let k=r.step;while(k!==null){ids.unshift(k);k=by.get(k).parent}paths.push({step:r.step,ids,depth:ids.length,parent_path_duration_sum_ms:ids.reduce((s,k)=>s+by.get(k).duration_ms,0)});if(r.parent!==null){const p=by.get(r.parent),known=r.start_ms!==null&&p.start_ms!==null;edges.push({parent:p.step,child:r.step,both_timed:known,child_starts_before_parent:known?r.start_ms<p.start_ms:null,child_ends_after_parent:known?r.start_ms+r.duration_ms>p.start_ms+p.duration_ms:null})}}
  const timed=rows.filter(r=>r.start_ms!==null),boundaries=new Map();const event=x=>{if(!boundaries.has(x))boundaries.set(x,{starts:[],ends:[],points:[]});return boundaries.get(x)};
  for(const r of timed){const a=r.start_ms,b=a+r.duration_ms;if(a===b)event(a).points.push(r.step);else{event(a).starts.push(r.step);event(b).ends.push(r.step)}}
  const points=[...boundaries.keys()].sort((a,b)=>a-b),events=[],segments=[],active=new Set();
  points.forEach((x,i)=>{const e=boundaries.get(x),ends=e.ends.sort(),starts=e.starts.sort(),zero=e.points.sort();for(const k of ends)active.delete(k);for(const k of starts)active.add(k);events.push({at_ms:x,ends,starts,points:zero,active_after:[...active].sort()});if(i+1<points.length){const y=points[i+1],d=y-x;segments.push({start_ms:x,end_ms:y,width_ms:d,active_ids:[...active].sort(),count:active.size,covered_ms:active.size?d:0,weighted_ms:d*active.size})}});
  const span=points.length?points.at(-1)-points[0]:null,busy=segments.reduce((s,r)=>s+r.covered_ms,0),weighted=segments.reduce((s,r)=>s+r.weighted_ms,0),unknown=rows.filter(r=>r.start_ms===null).map(r=>r.step).sort();
  const timing={complete:!unknown.length,timed_ids:timed.map(r=>r.step).sort(),unknown_ids:unknown,events,segments,recorded_span_ms:span,busy_union_ms:timed.length?busy:null,uncovered_ms:span===null?null:span-busy,timed_duration_sum_ms:timed.reduce((s,r)=>s+r.duration_ms,0),step_duration_sum_ms:rows.reduce((s,r)=>s+r.duration_ms,0),weighted_area_ms:weighted,overlap_excess_ms:timed.length?weighted-busy:null,peak_recorded_spans:Math.max(0,...segments.map(s=>s.count))};
  const ordered=[...rows].sort((a,b)=>a.duration_ms-b.duration_ms||(a.step<b.step?-1:a.step>b.step?1:0)),rank=(rows.length-1)*.95,lo=Math.floor(rank),hi=Math.min(lo+1,rows.length-1),w=rank-lo;
  const p95={ordered:ordered.map(r=>({step:r.step,duration_ms:r.duration_ms})),rank,low_index:lo,high_index:hi,high_weight:w,low_value:ordered[lo].duration_ms,high_value:ordered[hi].duration_ms,value_ms:ordered[lo].duration_ms*(1-w)+ordered[hi].duration_ms*w};
  runs.push({run_id:run,graph:{roots,order,depth:Object.fromEntries(depth),max_depth:Math.max(0,...depth.values())},paths,parent_time_relations:edges,timing,p95,errors:rows.filter(r=>r.kind==='error'||r.status!=='ok').map(r=>r.step)})
 }
 return {schema_version:1,spec:{events:source},records,runs}
}
