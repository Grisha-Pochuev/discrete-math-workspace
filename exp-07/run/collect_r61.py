#!/usr/bin/env python3
import argparse,glob,json,sys
from pathlib import Path
ap=argparse.ArgumentParser(); ap.add_argument('--root',default='bundles'); ap.add_argument('--output',default='out/aggregate.json'); ap.add_argument('--expected',type=int,default=20); a=ap.parse_args()
packages=[]; errors=[]
for p in glob.glob(f'{a.root}/**/package.json',recursive=True):
    try:q=json.load(open(p));q['_path']=p;packages.append(q)
    except Exception as e: errors.append({'path':p,'error':str(e)})
valid=[q for q in packages if q.get('engine')=='r61' and q.get('schema')==4]
ids=sorted(q.get('id') for q in valid if isinstance(q.get('id'),int)); missing=[i for i in range(a.expected) if i not in ids]
params={k:sorted({str(q.get(k)) for q in valid}) for k in ('parts','N','pmax','filters','wheel','wheel_res','source')}
ce=[]
if len(valid)!=a.expected: ce.append(f'package_count={len(valid)} expected={a.expected}')
if ids!=list(range(a.expected)): ce.append(f'ids={ids}')
for k,v in params.items():
    if len(v)!=1: ce.append(f'{k}_values={v}')
for q in valid:
    i=q['id']
    if q.get('parts')!=a.expected: ce.append(f'id={i} bad_parts')
    if q.get('scientific_exit')!=0: ce.append(f'id={i} exit={q.get("scientific_exit")}')
    if not q.get('complete_no_survivor'): ce.append(f'id={i} incomplete')
    if q.get('partial'): ce.append(f'id={i} partial')
    if q.get('survivors')!=0: ce.append(f'id={i} survivors={q.get("survivors")}')
    if q.get('done')!=q.get('expected') or q.get('assigned')!=q.get('expected'): ce.append(f'id={i} expected/assigned/done mismatch')
if valid and len(params['N'])==1:
    N=int(params['N'][0]); W=16943706; R=(0,1,822511,16943705); total=0
    for i in range(a.expected):
        e=0
        for r in R:
            if r>N: continue
            k0=max(0,(2-r+W-1)//W); kmax=(N-r)//W
            if k0>kmax: continue
            rem=k0%a.expected
            if rem!=i: k0+=(i+a.expected-rem)%a.expected
            if k0<=kmax: e+=2*((kmax-k0)//a.expected+1)
        total+=e
        m=[q for q in valid if q.get('id')==i]
        if len(m)==1 and m[0].get('expected')!=e: ce.append(f'id={i} arithmetic_expected={e} package_expected={m[0].get("expected")}')
else: total=None
out={'schema':4,'engine':'r61','packages_seen':len(packages),'valid_packages':len(valid),'validated_ids':ids,'missing_ids':missing,
'parameter_sets':params,'tested_signed_indices':sum(int(q.get('done',0)) for q in valid),'arithmetic_total':total,
'survivors':sum(int(q.get('survivors',0)) for q in valid),'parse_errors':errors,'coverage_errors':ce,'complete_no_survivor':not errors and not ce}
Path(a.output).parent.mkdir(parents=True,exist_ok=True); Path(a.output).write_text(json.dumps(out,sort_keys=True,indent=2)+'\n'); print(json.dumps(out,sort_keys=True))
if errors or ce: sys.exit(1)
