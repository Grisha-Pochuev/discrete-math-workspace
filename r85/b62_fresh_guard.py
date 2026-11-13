"""Fail-closed admission for one fresh paired-geometry experiment.
No network, writes, solver calls or parent transformations happen in this module.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import subprocess


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# Overrides accepted by the old generic driver are deliberately unavailable.
FORBIDDEN = ('LOCAL HF NW DRP RO SMS SGF NM NG EXP EXL EXN EK ESEED IX S2 S2R AG BIK AP AV LP XU FX DS QW RW MS RS CK CXX'.split())


def check_plan(plan, env, argv, now):
    require(plan.get('schema') == 'gaia-paired-fresh-v1', 'schema')
    require(plan.get('status') == 'APPROVED_ONE_SHOT', 'inactive plan')
    mode=plan.get('mode')
    require(mode in ('production','smoke'), 'explicit mode')
    nj,seconds=(20,20700) if mode=='production' else (1,1200)
    require(plan.get('timing') == {'export_reserve':360,'min_search':600,'hardstop_grace':30}, 'timing')
    require(plan.get('budget') == {'jobs':nj,'islands_per_job':4,'np':100,'nk':30,'seconds':seconds,'automatic_repeats':0}, 'budget')
    require(plan.get('parent_run') == 0, 'fresh cannot have native parent')
    require(plan.get('baseline_price') == 288843498, 'baseline')
    require(plan.get('policy') == {'geometry':'paired80k','initialization':'fresh-native-k0-base-k123-late-injection','exchange':'none','restart':'none','operator':'natural','abcap':'single'}, 'policy')
    require(len(argv)==3, 'arguments')
    seed=int(argv[1]); require(int(argv[2])==seconds, 'time')
    require(env.get('W')=='4' and env.get('Q')==f"100,30,{plan['cycle']}", 'W/Q')
    require(env.get('PERT')=='25' and env.get('MT')=='3000' and env.get('TLX')=='0', 'workflow inputs')
    require(not any(k in env for k in FORBIDDEN), 'unsupported override')
    require(not any(k.startswith('GA_') for k in env), 'native override')
    require(env.get('GITHUB_REPOSITORY')=='Grisha-Pochuev/discrete-math-workspace', 'repository')
    require(env.get('GITHUB_RUN_ATTEMPT')=='1', 'rerun forbidden')
    require(env.get('GITHUB_EVENT_NAME')=='workflow_dispatch', 'event')
    require(env.get('GITHUB_RUN_ID','').isdigit() and int(env['GITHUB_RUN_ID'])>0, 'run identity')
    require(len(env.get('GITHUB_SHA',''))==40 and all(c in '0123456789abcdef' for c in env['GITHUB_SHA']), 'public head identity')
    require(plan['activation_epoch'] <= now <= plan['expiry_epoch'], 'admission window')
    require(0 < plan['expiry_epoch']-plan['activation_epoch'] <= 3600, 'admission window length')
    jobs=plan['jobs']; require(len(jobs)==nj, 'job count')
    ids=[j['seed'] for j in jobs]; require(len(set(ids))==nj and all(type(j['geometry_index']) is int and 0<=j['geometry_index']<20 for j in jobs), 'job mapping')
    if mode=='production':
        require(sorted(j['geometry_index'] for j in jobs)==list(range(20)), 'full geometry coverage')
    if mode=='production':
        require(sorted(ids)==list(range(min(ids),min(ids)+20)) and min(ids)%20==0, 'consecutive aligned jobs')
    require(all(j['geometry_index']==j['seed']%20 for j in jobs), 'driver mapping')
    require(all(len(j['seeds'])==4 for j in jobs), 'island seed count')
    seeds=[s for j in jobs for s in j['seeds']]
    require(all(type(s) is int and 0<s<2**31 for s in seeds), 'seed range')
    require(len(set(seeds))==nj*4 and len({s&65535 for s in seeds})==nj*4, 'seed collisions')
    historical=plan['excluded_seeds']; require(not(set(seeds)&set(historical)) and not({s&65535 for s in seeds}&{s&65535 for s in historical}), 'historical seed collision')
    pairs={}
    for j in jobs:
        require(j['pair']==j['geometry_index']//2 and j['arm']==('shift' if j['geometry_index']%2 else 'control'), 'geometry pair/arm binding')
        pairs.setdefault(j['pair'],[]).append(j['arm'])
    if mode=='production': require(len(pairs)==10 and all(sorted(v)==['control','shift'] for v in pairs.values()), 'pairs')
    require(seed in ids, 'unlisted job')
    return dict(plan, job=jobs[ids.index(seed)])


def preflight(driver):
    started=time.time()
    root=Path(driver).resolve().parent
    plan=json.loads((root/'b62_fresh_plan.json').read_text())
    admitted=check_plan(plan,os.environ,sys.argv,time.time())
    require(set(plan['source_files'])=={Path(driver).name,'b62_fresh_guard.py','build_g25.py','g24.bin','ab_cap_patch.py'}, 'source inventory')
    for name,h in plan['source_files'].items():
        require(digest(root/name)==h, 'source SHA '+name)
    require(not Path('p').exists() and not Path('q').exists(), 'parent material present')
    require(not Path('o').exists(), 'output exists')
    wd=Path('wd')
    require(not wd.exists() or {p.name for p in wd.iterdir()} <= {'a','b'}, 'dirty workdir')
    if os.environ.get('GITHUB_EVENT_PATH'):
        e=json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
        expected={'n':str(plan['budget']['jobs']),'o':str(min(j['seed'] for j in plan['jobs'])),'t':str(plan['budget']['seconds']),'mt':'3000','pert':'25','f':Path(driver).name,'q':f"100,30,{plan['cycle']}",'pr':'0','pb':'0','tl':'0'}
        require(e.get('inputs')==expected,'dispatch inputs')
    else:
        raise ValueError('missing workflow event')
    require(digest(wd/'a')=='0a613505e22d15f67372824568bce53255b088d677889bc9990299afea5735b4','coordinates missing/corrupt')
    require(digest(wd/'b')=='ab3c6fa0ff96eae12b9b63c8f8654b839e90621f2acc866c18cdf54720b4e852','base tour gzip missing/corrupt')
    generated=root/'g25.bin'
    require(not generated.exists(), 'generated geometry already exists')
    subprocess.run([sys.executable,str(root/'build_g25.py'),'--coords',str(wd/'a'),'--g24',str(root/'g24.bin'),'--out',str(generated),'--expected-sha',plan['geometry_sha256']],check=True,timeout=600)
    require(digest(generated)==plan['geometry_sha256'],'generated geometry SHA')
    admitted['started_epoch']=started
    admitted['runtime_identity']={k:os.environ[k] for k in ('GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT','GITHUB_SHA')}
    return admitted


def validate_geometry(plan,g,X,R,price,seed):
    import numpy as np
    require(price==plan['baseline_price'] and len(X)==2079471, 'global baseline')
    require(set(g.files)=={'s','dr','da','i','o'}, 'geometry schema')
    offsets=g['o']; ids=g['i']
    require(np.array_equal(offsets,np.arange(21)*80000) and len(ids)==1600000, 'geometry dimensions')
    for i in range(20):
        a=ids[offsets[i]:offsets[i+1]]
        require(np.issubdtype(a.dtype,np.integer) and len(np.unique(a))==80000 and int(a.min())>=0 and int(a.max())<len(X), 'geometry vertices')
    require(np.array_equal(np.sort(R),np.arange(len(X))), 'global cycle')
    require(hashlib.sha256(np.asarray(R,dtype='<i8').tobytes()).hexdigest()==plan['baseline_tour_sha256'], 'baseline tour identity')


def finalize(output,report,npop,islands):
    output=Path(output)
    exits=report['child_exits']
    okay=len(exits)==islands and {e['k'] for e in exits}==set(range(islands)) and all(e['rc']==0 for e in exits)
    okay=okay and not report.get('runtime_errors')
    okay=okay and len(report['isl'])==islands and all(x.get('np')==npop and x.get('tag') in ('deadline','done') for x in report['isl'])
    expected=[f'{p}{k}.bin' for k in range(islands) for p in ('c','u')]
    okay=okay and all((output/f).is_file() and (output/f).stat().st_size>0 for f in expected)
    receipt={'status':'COMPLETE_PENDING_INDEPENDENT_AUDIT' if okay else 'INCOMPLETE','files':{p.name:{'bytes':p.stat().st_size,'sha256':digest(p)} for p in sorted(output.iterdir()) if p.is_file()},'child_exits':exits}
    (output/'completion.json').write_text(json.dumps(receipt,sort_keys=True,indent=2))
    require(okay,'incomplete or failed child; artifacts retained; no scientific PASS')


def supervise(setup, islands, inspect, report, hardstop, on_exit=lambda: None,
              clock=time.time, sleep=time.sleep, interval=5, stop_grace=30):
    """Own only returned Popen handles; never discover or signal unrelated PIDs.
    setup must close its log if Popen fails. On any error stop owned children,
    close logs and return to caller for per-island checkpoint harvest.
    """
    owned={}; observed=set(); errors=report.setdefault('runtime_errors',[])
    def error(where, exc):
        errors.append({'where':where,'error':type(exc).__name__+': '+str(exc)})
    def observe():
        for k,(pr,lf) in owned.items():
            rc=pr.poll()
            if rc is not None and k not in observed:
                observed.add(k)
                report['child_exits'].append({'k':k,'trial':0,'pid':pr.pid,'rc':rc,'observed_at':clock()})
                try: on_exit()
                except Exception as exc: error('exit_receipt',exc)
    try:
        for k in range(islands):
            if clock()>=hardstop: raise TimeoutError('launch hardstop')
            owned[k]=setup(k)
        while True:
            observe()
            if len(observed)==len(owned): break
            if clock()>=hardstop: raise TimeoutError('owned child hardstop')
            sleep(min(interval,max(0,hardstop-clock())))
    except Exception as exc:
        error('supervision',exc)
    finally:
        # A returned Popen owns and polls/reaps its child: no numeric PID census.
        for k,(pr,lf) in owned.items():
            if pr.poll() is None:
                try: pr.terminate()
                except Exception as exc: error('terminate '+str(k),exc)
        end=clock()+stop_grace
        while any(pr.poll() is None for pr,lf in owned.values()) and clock()<end:
            sleep(min(1,max(0,end-clock())))
        for k,(pr,lf) in owned.items():
            if pr.poll() is None:
                try: pr.kill(); pr.wait(timeout=5)
                except Exception as exc: error('kill/wait '+str(k),exc)
        observe()
        for k,(pr,lf) in owned.items():
            try: lf.close()
            except Exception as exc: error('log close '+str(k),exc)
    report['harvest_allowed']=all(pr.poll() is not None for pr,lf in owned.values())
    if report['harvest_allowed']:
        # Potentially expensive full-tour validation cannot delay process watchdog.
        # Inspect only immutable outputs after all owned children have exited.
        for k in owned:
            try: inspect(k)
            except Exception as exc: error('improvement harvest '+str(k),exc)
    if not report['harvest_allowed']:
        error('harvest',RuntimeError('owned child remains; do not read mutable checkpoints'))
    return owned
