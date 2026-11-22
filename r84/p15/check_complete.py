import json,sys
from pathlib import Path
p=Path(sys.argv[1]);m=json.loads((p/'m.json').read_text())
def need(ok,msg):
 if not ok: raise ValueError(msg)
need(m['status']=='complete' and len(m['workers'])==4,'four workers')
for i in range(4):
 r=json.loads((p/f'{i:02d}'/'run.json').read_text());b=r['branches']['2'];s=b['kernel_stats']
 need(r['complete'] and r['seconds_per_branch']==int(sys.argv[2]) and b['status']=='completed_budget' and b['seconds']>=int(sys.argv[2]) and b['returncode']==0,'complete fire duration')
 need(b['search_exercised'] and s['cap_hits']==s['single_fallbacks']==0 and s['injection_generation']==-1,'operator')
print('FOUR_FULL_BUDGETS_COMPLETE')

