'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{spawn,execFileSync}=require('node:child_process'),{waitForDebugger}=require('./chrome_support.cjs');
const delay=ms=>new Promise(r=>setTimeout(r,ms));
function compare(a,b,p='root'){assert.equal(typeof a,typeof b,p);if(typeof a==='number')assert.ok(Number.isFinite(b)&&Math.abs(a-b)<=1e-11*Math.max(1,Math.abs(a),Math.abs(b)),p);else if(a===null||typeof a!=='object')assert.equal(a,b,p);else{assert.deepEqual(Object.keys(a).sort(),Object.keys(b).sort(),p);for(const k of Object.keys(a))compare(a[k],b[k],p+'.'+k);}}
test('actual Chrome complete interval/graph witnesses, full records and timeline marks',{timeout:180000},async()=>{
 const server=require('node:http').createServer((req,res)=>{try{const file=path.join(__dirname,'../docs',req.url==='/'?'index.html':req.url);const types={'.html':'text/html','.js':'application/javascript','.css':'text/css','.json':'application/json'};res.setHeader('Content-Type',types[path.extname(file)]||'text/plain');res.end(fs.readFileSync(file));}catch(e){res.statusCode=404;res.end('not found');}});await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const profile=fs.mkdtempSync(path.join(os.tmpdir(),'agenttrace-paired-')),browser=spawn(process.env.CHROME_BIN||'google-chrome',['--headless','--no-sandbox','--disable-gpu','--disable-extensions','--disable-dev-shm-usage','--remote-debugging-port=0',`--user-data-dir=${profile}`,'about:blank'],{stdio:['ignore','ignore','pipe']});let ws,startupError,diagnostics='';browser.on('error',e=>startupError=e);browser.stderr.on('data',d=>diagnostics=(diagnostics+d).slice(-4000));
 try{for(let i=0;i<1200&&!startupError&&browser.exitCode===null&&!fs.existsSync(path.join(profile,'DevToolsActivePort'));i++)await delay(25);assert.ok(fs.existsSync(path.join(profile,'DevToolsActivePort')),startupError?.message||diagnostics||'Chrome unavailable');const port=fs.readFileSync(path.join(profile,'DevToolsActivePort'),'utf8').split('\n')[0],tab=await waitForDebugger(`http://127.0.0.1:${port}/json/list`,{alive:()=>browser.exitCode===null&&!startupError});ws=new WebSocket(tab.webSocketDebuggerUrl);await new Promise((res,rej)=>{ws.onopen=res;ws.onerror=rej;});let seq=0;const pending=new Map();ws.onmessage=e=>{const m=JSON.parse(e.data);if(pending.has(m.id)){const {res,rej}=pending.get(m.id);pending.delete(m.id);m.error?rej(Error(JSON.stringify(m.error))):res(m.result);}};const call=(method,params={})=>new Promise((res,rej)=>{const id=++seq;pending.set(id,{res,rej});ws.send(JSON.stringify({id,method,params}));});const js=async expression=>{const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
 await call('Page.enable');await call('Page.navigate',{url:process.env.AGENTTRACE_URL||`http://127.0.0.1:${server.address().port}/`});
 for(let i=0;i<500;i++){if(await js('Boolean(window.currentAudit)'))break;await delay(20);}assert.ok(await js('window.currentAudit'));


 const fixtures=JSON.parse(fs.readFileSync(path.join(__dirname,'../docs/audit.json'),'utf8'));
 const set=async(id,value,event='input')=>js(`document.getElementById(${JSON.stringify(id)}).value=${JSON.stringify(String(value))};document.getElementById(${JSON.stringify(id)}).dispatchEvent(new Event(${JSON.stringify(event)}))`);
 const table=async id=>js(`Array.from(document.querySelectorAll('#'+${JSON.stringify(id)}+' tr'),tr=>Array.from(tr.cells,c=>c.textContent))`);
 const ids=v=>v.length?v.join(', '):'none',yes=v=>v===null?'unknown':v?'yes':'no';let runs=0,endpoints=0,segments=0,paths=0,records=0,relations=0,marks=0;
 for(let i=0;i<fixtures.cases.length;i++){
  const report=fixtures.cases[i].report;
  await set('fixture',i,'change');assert.equal(await js('currentAudit'),null);assert.equal(await js('document.getElementById("results").hidden'),true);assert.equal(await js('document.getElementById("download").disabled'),true);
  await js('document.getElementById("controls").requestSubmit()');compare(await js('currentAudit'),report);
  for(const run of report.runs){
   runs++;await set('run',run.run_id,'change');const t=run.timing;
   assert.deepEqual(await table('endpoints'),t.events.map(e=>[e.at_ms,ids(e.ends),ids(e.starts),ids(e.points),ids(e.active_after)].map(String)));endpoints+=t.events.length;
   assert.deepEqual(await table('segments'),t.segments.map(s=>[s.start_ms,s.end_ms,s.width_ms,ids(s.active_ids),s.count,s.covered_ms,s.weighted_ms].map(String)));segments+=t.segments.length;
   assert.deepEqual(await table('paths'),run.paths.map(p=>[p.step,p.ids.join(' → '),p.depth,p.parent_path_duration_sum_ms].map(String)));paths+=run.paths.length;
   assert.deepEqual(await table('relations'),run.parent_time_relations.map(e=>[e.parent,e.child,yes(e.both_timed),yes(e.child_starts_before_parent),yes(e.child_ends_after_parent)]));relations+=run.parent_time_relations.length;
   assert.deepEqual(await table('ordered'),run.p95.ordered.map((r,i)=>[i,r.step,r.duration_ms].map(String)));
   for(const [id,value] of [['sum',t.step_duration_sum_ms],['span',t.recorded_span_ms],['busy',t.busy_union_ms],['peak',t.peak_recorded_spans]])assert.equal(await js(`document.getElementById(${JSON.stringify(id)}).textContent`),value===null?'undefined':String(value));
   const rows=report.records.filter(r=>r.run_id===run.run_id);
   for(const r of rows){await set('inspect',r.step,'change');assert.deepEqual(JSON.parse(await js('document.getElementById("record").textContent')),r);records++}
   const cw=await js('Math.max(240,document.getElementById("chart").parentElement.clientWidth-18)'),compact=cw<600,left=compact?20:180,plot=cw-left-24,origin=t.events.length?Math.min(...t.events.map(e=>e.at_ms)):0,denom=t.recorded_span_ms||1;
   const shown=await js('Array.from(document.querySelectorAll("#chart [data-step]"),e=>({step:e.dataset.step,start:Number(e.dataset.start),duration:Number(e.dataset.duration),tag:e.tagName,x:Number(e.getAttribute(e.tagName==="rect"?"x":"cx")),y:Number(e.getAttribute(e.tagName==="rect"?"y":"cy")),width:e.tagName==="rect"?Number(e.getAttribute("width")):null}))');
   const expected=rows.flatMap((r,i)=>r.start_ms===null?[]:[{step:r.step,start:r.start_ms,duration:r.duration_ms,tag:r.duration_ms?'rect':'circle',x:left+(r.start_ms-origin)/denom*plot,y:52+i*(compact?64:44)-(r.duration_ms?5:0),width:r.duration_ms?r.duration_ms/denom*plot:null}]);compare(shown,expected);marks+=expected.length;
  }
  assert.equal(await js('document.querySelectorAll("main img, main script:not([type=module])").length'),0);
 }
 await set('events','[{"run_id":"r","step":"a","parent":"a","kind":"tool","name":"x"}]');await js('document.getElementById("controls").requestSubmit()');assert.equal(await js('currentAudit'),null);
 await set('fixture',1,'change');await js('document.getElementById("controls").requestSubmit()');
 await js('HTMLAnchorElement.prototype.click=function(){window.downloaded={name:this.download,url:this.href}};URL.revokeObjectURL=function(){}');await js('document.getElementById("download").click()');assert.deepEqual(await js('fetch(downloaded.url).then(r=>r.json())'),await js('currentAudit'));
 for(const width of [320,390,1280]){await call('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:width<700});await js('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');assert.ok(await js('document.documentElement.scrollWidth<=innerWidth'),'overflow '+width)}
 console.log(JSON.stringify({cases:fixtures.cases.length,runs,endpoints,segments,paths,records,relations,marks,exports:1,widths:[320,390,1280]}));
 if(process.env.AGENTTRACE_SCREENSHOT){const width=Number(process.env.AGENTTRACE_WIDTH||1280);await call('Emulation.setDeviceMetricsOverride',{width,height:1200,deviceScaleFactor:1,mobile:width<700});await js('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');await js('document.activeElement.blur();window.scrollTo(0,0)');if(process.env.AGENTTRACE_EXPAND)await js('document.querySelectorAll("details").forEach(e=>e.open=true)');const m=await call('Page.getLayoutMetrics'),image=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip:{x:0,y:0,width,height:m.cssContentSize.height,scale:1}});fs.writeFileSync(process.env.AGENTTRACE_SCREENSHOT,Buffer.from(image.data,'base64'))}
 }finally{server.close();if(ws)ws.close();if(browser.pid&&browser.exitCode===null){browser.kill('SIGTERM');await new Promise(r=>browser.once('exit',r));}await fs.promises.rm(profile,{recursive:true,force:true,maxRetries:10,retryDelay:200});}
});
