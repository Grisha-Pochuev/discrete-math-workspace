#!/usr/bin/env python3
from __future__ import annotations
import argparse, gzip, hashlib, json, random, time
from collections import Counter
from pathlib import Path
import run000_core as core
from run000_core import atomic_write_gz, build_system, scan_all_assignments, random_disjoint_factor_system, system_signature, merge_scan, adversarial_search
from run000_orbits import n10_orbit_representatives

def worker(args):
    started=time.monotonic(); deadline=started+args.seconds; rng=random.Random(args.seed+1000003*args.worker_id)
    result={'schema_version':1,'run_index':0,'worker_id':args.worker_id,'seconds_requested':args.seconds,
            'seed':args.seed+1000003*args.worker_id,'technical_status':'RUNNING','n10':{},
            'frontier':{'systems_completed':0,'systems_partial':0,'assignments_checked':0,'trap_cases':0,
                        'h_only_failures':0,'corrected_failures':0,'minimum_h_safe':None,'minimum_full_safe':None,'hard_cases':[]}}
    reps,digest,meta=n10_orbit_representatives(); assigned=[i for i in range(len(reps)) if i%args.worker_count==args.worker_id]
    n10={'orbit_count':len(reps),'orbit_digest':digest,**meta,'assigned_orbits':assigned,'completed_orbits':[],
         'assignments_checked':0,'trap_cases':0,'h_only_failures':0,'corrected_failures':0,
         'minimum_h_safe':None,'minimum_full_safe':None,'hard_cases':[]}
    result['n10']=n10; atomic_write_gz(args.output,result)
    for orbit_index in assigned:
        if core.STOP or time.monotonic()>=deadline: break
        factors=reps[orbit_index]; scan=scan_all_assignments(build_system(10,factors),deadline)
        if not scan['complete']: break
        n10['completed_orbits'].append(orbit_index)
        for key in ('assignments_checked','trap_cases','h_only_failures','corrected_failures'): n10[key]+=scan[key]
        for key in ('minimum_h_safe','minimum_full_safe'):
            val=scan[key]
            if val is not None: n10[key]=val if n10[key] is None else min(n10[key],val)
        for rec in scan['hard_cases']:
            rec=dict(rec); rec['orbit_index']=orbit_index; rec['factors']=[[list(e) for e in m] for m in factors]; n10['hard_cases'].append(rec)
        n10['hard_cases'].sort(key=lambda x:(x['full_safe'],x['h_safe'],-x['trap_count'])); del n10['hard_cases'][10:]
        atomic_write_gz(args.output,result)
    wid=args.worker_id
    if wid<40: mode,n='n12_exhaustive',12
    elif wid<60: mode,n='n14_exhaustive',14
    elif wid<72: mode,n='n16_adversarial',16
    else: mode,n='n18_adversarial',18
    result['frontier'].update(mode=mode,n=n); systems=0
    while not core.STOP and time.monotonic()<deadline:
        factors,remainder=random_disjoint_factor_system(n,rng); system=build_system(n,factors,remainder); systems+=1
        if 'exhaustive' in mode:
            scan=scan_all_assignments(system,deadline)
            for rec in scan.get('hard_cases',[]):
                rec['system_signature']=system_signature(factors,remainder); rec['factors']=[[list(e) for e in m] for m in factors]
            merge_scan(result['frontier'],scan); result['frontier']['sampled_systems']=systems; atomic_write_gz(args.output,result)
            if not scan['complete']: break
        else:
            checked,hard=adversarial_search(system,rng,deadline); f=result['frontier']; f['assignments_checked']+=checked; f['sampled_systems']=systems
            if hard is not None:
                hard['system_signature']=system_signature(factors,remainder); hard['factors']=[[list(e) for e in m] for m in factors]
                f['hard_systems_with_trap']=f.get('hard_systems_with_trap',0)+1
                for key,src in (('minimum_h_safe','h_safe'),('minimum_full_safe','full_safe')):
                    f[key]=hard[src] if f[key] is None else min(f[key],hard[src])
                if hard['h_safe']==0: f['hard_systems_h_only_failure']=f.get('hard_systems_h_only_failure',0)+1
                if hard['full_safe']==0: f['corrected_failures']+=1
                f['hard_cases'].append(hard); f['hard_cases'].sort(key=lambda x:(x['full_safe'],x['h_safe'],-x['trap_count'])); del f['hard_cases'][10:]
            if systems%8==0 or f['corrected_failures']: atomic_write_gz(args.output,result)
    result['technical_status']='SUCCESS'; result['stop_reason']='signal' if core.STOP else 'time_limit'; result['elapsed_seconds']=time.monotonic()-started
    atomic_write_gz(args.output,result); return 0

def self_test():
    factors=(((0,2),(1,4),(3,5)),((0,3),(1,5),(2,4)),((0,4),(1,3),(2,5))); remainder=((0,1),(2,3),(4,5)); duplicated=(1,0,2,1,0,2)
    ev=core.evaluate_assignment(build_system(6,factors,remainder),duplicated); assert ev is not None and ev[:3]==(1,0,3),ev
    reps,digest,meta=n10_orbit_representatives(); assert len(reps)==1108 and meta=={'allowed_matchings':544,'labelled_factor_triples':23019264}
    print(json.dumps({'self_test':'ok','n10_orbits':1108,'orbit_digest':digest,**meta},indent=2)); return 0

def load_worker(path):
    with gzip.open(path,'rt',encoding='utf-8') as f: return json.load(f)

def verify_worker(path,expect=None):
    d=load_worker(path); assert d['schema_version']==1 and d['n10']['orbit_count']==1108 and d['n10']['labelled_factor_triples']==23019264
    if expect is not None: assert d['worker_id']==expect,d
    assert d['technical_status'] in ('RUNNING','SUCCESS')
    print(json.dumps({'worker_id':d['worker_id'],'technical_status':d['technical_status'],'n10_completed_orbits':len(d['n10'].get('completed_orbits',[])),
                      'frontier_mode':d.get('frontier',{}).get('mode'),'frontier_assignments':d.get('frontier',{}).get('assignments_checked',0)},indent=2)); return 0

def smoke_collect(inp,out):
    d=load_worker(inp); assert d['worker_id']==0 and d['n10']['orbit_count']==1108 and len(d['n10']['completed_orbits'])>=1
    s={'schema_version':1,'smoke_passed':True,'worker_id':0,'orbit_digest':d['n10']['orbit_digest'],'n10_completed_orbits':len(d['n10']['completed_orbits']),
       'n10_corrected_failures':d['n10']['corrected_failures'],'frontier_mode':d['frontier'].get('mode'),'frontier_assignments_checked':d['frontier'].get('assignments_checked',0),
       'technical_status':d['technical_status']}
    Path(out).write_text(json.dumps(s,indent=2,sort_keys=True)+'\n'); print(json.dumps(s,indent=2,sort_keys=True)); return 0

def smoke_verify(path):
    d=json.loads(Path(path).read_text()); assert d['smoke_passed'] and d['n10_completed_orbits']>=1 and d['technical_status']=='SUCCESS' and len(d['orbit_digest'])==64
    print(json.dumps({'smoke_verify':'ok',**d},indent=2,sort_keys=True)); return 0

def collect(args):
    files=sorted(Path(args.artifacts).rglob('worker-*.json.gz'))
    if len(files)!=80: raise SystemExit(f'expected 80 worker files, found {len(files)}')
    workers=[load_worker(p) for p in files]; ids=sorted(int(w['worker_id']) for w in workers)
    if ids!=list(range(80)): raise SystemExit(f'worker ids mismatch: {ids}')
    digests={w['n10']['orbit_digest'] for w in workers}; counts={w['n10']['orbit_count'] for w in workers}
    if len(digests)!=1 or counts!={1108}: raise SystemExit('n10 orbit reconstruction mismatch')
    completed=[]; n10=Counter(); n10_min_h=n10_min_full=None; n10_hard=[]
    for w in workers:
        completed.extend(w['n10'].get('completed_orbits',[]))
        for k in ('assignments_checked','trap_cases','h_only_failures','corrected_failures'): n10[k]+=int(w['n10'].get(k,0) or 0)
        for k in ('minimum_h_safe','minimum_full_safe'):
            v=w['n10'].get(k)
            if v is not None:
                if k=='minimum_h_safe': n10_min_h=v if n10_min_h is None else min(n10_min_h,v)
                else: n10_min_full=v if n10_min_full is None else min(n10_min_full,v)
        n10_hard.extend(w['n10'].get('hard_cases',[]))
    if sorted(completed)!=list(range(1108)): raise SystemExit(f'n10 coverage incomplete: {len(completed)} records, {len(set(completed))} unique')
    n10_hard.sort(key=lambda x:(x['full_safe'],x['h_safe'],-x['trap_count'])); n10_hard=n10_hard[:30]
    technical=Counter(w.get('technical_status','MISSING') for w in workers); modes=Counter(); by_mode={}; frontier_hard=[]
    for w in workers:
        f=w.get('frontier',{}); mode=f.get('mode','unknown'); modes[mode]+=1; m=by_mode.setdefault(mode,{'workers':0,'systems_completed':0,'systems_partial':0,'sampled_systems':0,'assignments_checked':0,'trap_cases':0,'h_only_failures':0,'corrected_failures':0,'minimum_h_safe':None,'minimum_full_safe':None})
        m['workers']+=1
        for k in ('systems_completed','systems_partial','sampled_systems','assignments_checked','trap_cases','h_only_failures','corrected_failures'): m[k]+=int(f.get(k,0) or 0)
        for k in ('minimum_h_safe','minimum_full_safe'):
            v=f.get(k)
            if v is not None: m[k]=v if m[k] is None else min(m[k],v)
        frontier_hard.extend(f.get('hard_cases',[]))
    frontier_hard.sort(key=lambda x:(x['full_safe'],x['h_safe'],-x['trap_count'])); frontier_hard=frontier_hard[:60]
    high_fail=sum(v['corrected_failures'] for v in by_mode.values()); accepted=(technical==Counter({'SUCCESS':80}))
    run_dir=Path(args.repo)/'fifth-approach'/'runs'/f'run-000-{args.run_id}'; run_dir.mkdir(parents=True,exist_ok=True)
    summary={'schema_version':1,'run_index':0,'run_id':int(args.run_id),'source_sha':args.source_sha,'accepted':accepted,
             'technical_status_counts':dict(technical),'worker_modes':dict(modes),'execution':{'jobs':20,'workers':80,'seconds_per_worker':21000},
             'n10_exact':{'orbit_count':1108,'orbit_digest':next(iter(digests)),'labelled_factor_triples':23019264,'orbit_coverage_complete':True,
                          'assignments_checked':n10['assignments_checked'],'trap_cases':n10['trap_cases'],'h_only_failures':n10['h_only_failures'],'corrected_failures':n10['corrected_failures'],
                          'minimum_h_safe':n10_min_h,'minimum_full_safe':n10_min_full},
             'frontier_by_mode':by_mode,'scientific_status':'corrected_exchange_counterexample_found' if n10['corrected_failures']+high_fail>0 else 'no_corrected_exchange_counterexample_observed'}
    (run_dir/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    with gzip.open(run_dir/'worker-results.json.gz','wt',encoding='utf-8',compresslevel=9) as f: json.dump(workers,f,separators=(',',':'),sort_keys=True)
    (run_dir/'hard-cases.json').write_text(json.dumps({'n10':n10_hard,'frontier':frontier_hard},indent=2,sort_keys=True)+'\n')
    checks=[]
    for name in ('summary.json','worker-results.json.gz','hard-cases.json'):
        checks.append(f"{hashlib.sha256((run_dir/name).read_bytes()).hexdigest()}  {name}")
    (run_dir/'checksums.sha256').write_text('\n'.join(checks)+'\n')
    control_path=Path(args.repo)/'fifth-approach'/'control.json'; control=json.loads(control_path.read_text())
    control.update(status='run_000_accepted' if accepted else 'run_000_collection_failed',enabled=False,completed_runs=1 if accepted else control.get('completed_runs',0),
                   last_run_id=int(args.run_id),last_run_index=0,next_run_index=1 if accepted else 0,active_spec_path=None,smoke_required=True,full_run_auto_launch_allowed=False,
                   tracking_enabled=False,recommended_next_action='review run-000 exact n10 result and high-n hard cases before selecting run 001')
    control_path.write_text(json.dumps(control,indent=2,sort_keys=True)+'\n'); print(json.dumps(summary,indent=2,sort_keys=True)); return 0 if accepted else 2

def main():
    ap=argparse.ArgumentParser(); sp=ap.add_subparsers(dest='cmd',required=True); sp.add_parser('self-test')
    p=sp.add_parser('worker'); p.add_argument('--worker-id',type=int,required=True); p.add_argument('--worker-count',type=int,default=80); p.add_argument('--seconds',type=int,required=True); p.add_argument('--seed',type=int,default=2026080800); p.add_argument('--output',required=True)
    v=sp.add_parser('verify-worker'); v.add_argument('--input',required=True); v.add_argument('--expect-worker',type=int)
    sc=sp.add_parser('smoke-collect'); sc.add_argument('--input',required=True); sc.add_argument('--output',required=True)
    sv=sp.add_parser('smoke-verify'); sv.add_argument('--input',required=True)
    c=sp.add_parser('collect'); c.add_argument('--repo',required=True); c.add_argument('--artifacts',required=True); c.add_argument('--run-id',required=True); c.add_argument('--source-sha',required=True)
    a=ap.parse_args()
    if a.cmd=='self-test': return self_test()
    if a.cmd=='worker': return worker(a)
    if a.cmd=='verify-worker': return verify_worker(a.input,a.expect_worker)
    if a.cmd=='smoke-collect': return smoke_collect(a.input,a.output)
    if a.cmd=='smoke-verify': return smoke_verify(a.input)
    if a.cmd=='collect': return collect(a)
if __name__=='__main__': raise SystemExit(main())
