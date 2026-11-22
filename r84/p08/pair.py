"""One two-arm comparison; fixed operator and identical random seed."""
import argparse,json,sys,time,math
from pathlib import Path

def need(x,m):
    if not x:raise ValueError(m)
def main():
    p=argparse.ArgumentParser()
    for k in ('source','prepared','output'):p.add_argument('--'+k,type=Path,required=True)
    for k in ('seconds','seed','index'):p.add_argument('--'+k,type=int,required=True)
    p.add_argument('--deadline',type=float,required=True);a=p.parse_args()
    sys.path.insert(0,str(a.source));import run_experiment as runner
    need(a.seconds in (60,9000),'budget');need(0<=a.index<20,'index');need(math.isfinite(a.deadline) and a.deadline-time.time()>=2*(a.seconds+30)+600,'pair deadline');need(not a.output.exists(),'fresh output');a.output.mkdir(parents=True)
    order=['c','t'] if a.index%2==0 else ['t','c'];receipt={'seed':a.seed,'seconds':a.seconds,'operator':2,'order':order,'arms':{},'complete':False,'external_preparation_injection':{'c':False,'t':True},'injected_zero_is_not_improvement':True}
    for arm in order:
        rc=runner.run(a.prepared/arm,a.prepared/'k',a.output/arm,a.seconds,a.seed,'2',6000,a.deadline)
        r=json.loads((a.output/arm/'run.json').read_text());branch=r['branches']['2'];st=branch['kernel_stats']
        need(rc==0 and r['complete'] and branch['search_exercised'],'complete search')
        need(st['children']>branch['initial_children'],'offspring progress')
        need(st['block2_attempts']>0 and st['cap_hits']==st['single_fallbacks']==0 and st['injection_generation']==-1,'operator contract')
        need(r['initial_base_present']==(arm=='t'),'initial condition')
        receipt['arms'][arm]={'returncode':rc,'initial_base_present':r['initial_base_present'],'initial_mean_gap':r['initial_mean_gap'],'checkpoint':branch['checkpoint'],'kernel_stats':st,'seconds':branch['seconds']}
        (a.output/'pair.json').write_text(json.dumps(receipt,indent=2)+'\n')
    receipt['complete']=True;(a.output/'pair.json').write_text(json.dumps(receipt,indent=2)+'\n')
if __name__=='__main__':main()
