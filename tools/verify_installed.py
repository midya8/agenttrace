import importlib.util,json,pathlib,sys
from agenttrace.audit import audit_trace
root=pathlib.Path(sys.argv[1]).resolve()
for name in ['agenttrace','agenttrace.__main__','agenttrace.analysis','agenttrace.cli','agenttrace.compare','agenttrace.models','agenttrace.parser','agenttrace.report','agenttrace.audit','agenttrace.graph','agenttrace.timing']:
 p=pathlib.Path(importlib.util.find_spec(name).origin).resolve();assert root not in p.parents,(name,p);assert 'site-packages' in p.parts,(name,p);print(name,p)
for c in json.loads((root/'docs/audit.json').read_text())['cases']:assert audit_trace(c['report']['spec'])==c['report']
print('Installed: eleven module origins and all 24 complete reports pass')
