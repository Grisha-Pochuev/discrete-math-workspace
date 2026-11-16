import argparse,json,sys,time
from pathlib import Path
p=argparse.ArgumentParser()
for k in ('source','prepared','output'):p.add_argument('--'+k,type=Path,required=True)
p.add_argument('--deadline',type=float,required=True);p.add_argument('--index',type=int,required=True);a=p.parse_args();root=Path(__file__).resolve().parent;cfg=json.loads((root/'admission.json').read_text())
def need(x,m):
 if not x:raise ValueError(m)
need(cfg['status']=='APPROVED_ONE_SHOT' and cfg['activation_epoch']<=time.time()<cfg['expiry_epoch'],'admission')
need(0<=a.index<20,'index');j=cfg['jobs'][a.index];need(j['i']==a.index and j['seconds']==19800 and j['operator']==2,'protocol')
need(a.deadline-time.time()>=21000,'save budget')
sys.path.insert(0,str(a.source));import run_experiment as runner
bundle='parent80' if j['vertices']==80000 else 'expanded150'
runner.run(a.prepared/bundle,a.prepared/'k',a.output,j['seconds'],j['seed'],'2',6000,a.deadline,production_admission=cfg)
r=json.loads((a.output/'run.json').read_text());b=r['branches']['2'];s=b['kernel_stats']
need(r['complete'] and b['returncode']==0 and b['search_exercised'],'run')
need(s['children']>b['initial_children'] and s['block2_attempts']>0,'search')
need(s['cap_hits']==s['single_fallbacks']==0 and s['injection_generation']==-1,'operator')
need(r['vertices']==j['vertices'] and not r['injection'] and not r['restart'],'identity')
