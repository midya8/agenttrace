export function parseInput(text){
 if(new TextEncoder().encode(text).length>131072)throw Error('Input exceeds 128 KiB');
 // Token walk prevents JSON.parse from silently losing duplicate keys or number spelling.
 let i=0;const ws=()=>{while(/\s/.test(text[i]||'')&&i<text.length)i++;};
 const string=()=>{const start=i++;while(i<text.length){if(text[i]==='\\'){i+=2;continue;}if(text[i++]==='"')return JSON.parse(text.slice(start,i));}throw Error('Unterminated string');};
 function value(depth){if(depth>8)throw Error('Nesting exceeds 8');ws();let ch=text[i];
  if(ch==='{'){i++;const keys=new Set();ws();if(text[i]==='}'){i++;return;}while(true){ws();if(text[i]!=='"')throw Error('Object key required');const k=string();if(keys.has(k))throw Error('Duplicate JSON key');keys.add(k);ws();if(text[i++]!==':')throw Error('Colon required');value(depth+1);ws();ch=text[i++];if(ch==='}')return;if(ch!==',')throw Error('Comma required');}}
  if(ch==='['){i++;ws();if(text[i]===']'){i++;return;}while(true){value(depth+1);ws();ch=text[i++];if(ch===']')return;if(ch!==',')throw Error('Comma required');}}
  if(ch==='"'){string();return;}
  const rest=text.slice(i);const literal=/^(true|false|null)/.exec(rest);if(literal){i+=literal[0].length;return;}
  const num=/^[^\s,\]}]+/.exec(rest);if(!num||!/^(0|[1-9][0-9]*)$/.test(num[0]))throw Error('Nonnegative integer numeric tokens only');i+=num[0].length;
 }
 value(0);ws();if(i!==text.length)throw Error('Trailing input');return JSON.parse(text);
}

// Independent complete-subset optimizer and Floyd-Warshall certificate reconstruction.
export const LIMITS='Hypothetical supplied half-open intervals and drop penalties, not trace deletion, inferred resource use, dependency repair, counterfactual runtime or production scheduling. Unknown timing cannot be certified; original trace analyzer and gates unchanged.';
function fields(x,keys){if(!x||typeof x!=='object'||Array.isArray(x)||Object.keys(x).sort().join('|')!==[...keys].sort().join('|'))throw Error('Exact fields required: '+keys.join(', '));}
function integer(x,max){if(!Number.isSafeInteger(x)||Object.is(x,-0)||x<0||x>max)throw Error('Bounded nonnegative integer required');}
export function normalize(x){fields(x,['capacity','intervals']);const r=structuredClone(x);integer(r.capacity,4);if(!Array.isArray(r.intervals)||r.intervals.length>12)throw Error('At most twelve intervals');const ids=new Set();for(const t of r.intervals){fields(t,['id','start','end','drop_penalty']);if(typeof t.id!=='string'||! /^[A-Za-z][A-Za-z0-9_-]{0,23}$/.test(t.id)||ids.has(t.id))throw Error('Distinct bounded ASCII interval ids required');ids.add(t.id);integer(t.start,1000000);integer(t.end,1000000);integer(t.drop_penalty,1000);if(t.end<t.start)throw Error('Interval end precedes start');}return r;}
function enumerate(rows){const times=[...new Set(rows.flatMap(t=>[t.start,t.end]))].sort((a,b)=>a-b);const best=Array.from({length:5},()=>({weight:-1,mask:0}));for(let mask=0;mask<2**rows.length;mask++){
 const chosen=rows.filter((_,i)=>mask&(2**i)),weight=chosen.reduce((v,t)=>v+t.drop_penalty,0);let peak=0;for(let j=0;j+1<times.length;j++){const midpoint=(times[j]+times[j+1])/2;peak=Math.max(peak,chosen.filter(t=>t.start<=midpoint&&midpoint<t.end).length);}
 for(let k=peak;k<5;k++){if(weight>best[k].weight||(weight===best[k].weight&&mask<best[k].mask))best[k]={weight,mask};}
 }return best;}
function network(rows,k,mask){const times=[...new Set(rows.filter(t=>t.start<t.end).flatMap(t=>[t.start,t.end]))].sort((a,b)=>a-b),n=times.length,scale=2**rows.length;const edges=[];
 for(let i=0;i+1<n;i++){const x=(times[i]+times[i+1])/2,active=rows.filter((t,j)=>(mask&2**j)&&t.start<=x&&x<t.end).length;edges.push({kind:'idle',id:'gap_'+i,from:i,to:i+1,capacity:k,cost:0,flow:k-active});}
 rows.forEach((t,i)=>{if(t.start<t.end)edges.push({kind:'interval',id:t.id,from:times.indexOf(t.start),to:times.indexOf(t.end),capacity:1,cost:-(t.drop_penalty*scale-2**i),flow:(mask&2**i)?1:0});});
 const residual=[];edges.forEach((e,i)=>{if(e.flow<e.capacity)residual.push({edge:i,direction:1,from:e.from,to:e.to,capacity:e.capacity-e.flow,cost:e.cost});if(e.flow)residual.push({edge:i,direction:-1,from:e.to,to:e.from,capacity:e.flow,cost:-e.cost||0});});
 // All-pairs shortest paths, not the producer's successive Bellman-Ford solver.
 const distance=Array.from({length:n},(_,i)=>Array.from({length:n},(_,j)=>i===j?0:Infinity));for(const a of residual)distance[a.from][a.to]=Math.min(distance[a.from][a.to],a.cost);
 for(let via=0;via<n;via++)for(let u=0;u<n;u++)for(let v=0;v<n;v++)distance[u][v]=Math.min(distance[u][v],distance[u][via]+distance[via][v]);
 const potentials=times.map((_,v)=>Math.min(0,...distance.map(d=>d[v]))||0);residual.forEach(a=>a.reduced_cost=a.cost+potentials[a.from]-potentials[a.to]);
 const cost=edges.reduce((v,e)=>v+e.flow*e.cost,0),dual_bound=(n?k*(potentials[n-1]-potentials[0]):0)+edges.reduce((v,e)=>v+e.capacity*Math.min(0,e.cost+potentials[e.from]-potentials[e.to]),0);
 if(cost!==dual_bound||residual.some(a=>a.reduced_cost<0)||edges.some(e=>e.flow<0||e.flow>e.capacity))throw Error('Certificate reconstruction failed');return{times,edges,potentials,residual,flow_value:n?k:0,cost,dual_bound,gap:cost-dual_bound};
}
export function capacityReport(input){const r=normalize(input),rows=r.intervals,best=enumerate(rows),total=rows.reduce((v,t)=>v+t.drop_penalty,0);
 const frontier=best.map((b,k)=>({capacity:k,retained_mask:b.mask,retained_ids:rows.filter((_,i)=>b.mask&2**i).map(t=>t.id),dropped_ids:rows.filter((_,i)=>!(b.mask&2**i)).map(t=>t.id),retained_penalty:b.weight,drop_penalty:total-b.weight}));
 const selected={...frontier[r.capacity],network:network(rows,r.capacity,best[r.capacity].mask)},keep=new Set(selected.retained_ids),boundaries=[...new Set(rows.flatMap(t=>[t.start,t.end]))].sort((a,b)=>a-b),segments=[];
 for(let j=0;j+1<boundaries.length;j++){const start=boundaries[j],end=boundaries[j+1],original_active=rows.filter(t=>t.start<=start&&start<t.end).map(t=>t.id),retained_active=original_active.filter(id=>keep.has(id));segments.push({start,end,original_active,retained_active,original_count:original_active.length,retained_count:retained_active.length,within_capacity:retained_active.length<=r.capacity});}
 const laneEnds=Array(r.capacity).fill(-1),lanes=new Map();rows.map((t,i)=>({...t,i})).sort((a,b)=>a.start-b.start||a.end-b.end||a.i-b.i).forEach(t=>{if(keep.has(t.id)&&t.start<t.end){const lane=laneEnds.findIndex(v=>v<=t.start);if(lane<0)throw Error('No feasible lane');laneEnds[lane]=t.end;lanes.set(t.id,lane);}});
 return{schema:1,input:r,tie_scale:2**rows.length,selected,frontier,intervals:rows.map(t=>({...t,retained:keep.has(t.id),point:t.start===t.end,lane:lanes.get(t.id)??null})),segments,original_peak:Math.max(0,...segments.map(s=>s.original_count)),retained_peak:Math.max(0,...segments.map(s=>s.retained_count)),limits:LIMITS};}
