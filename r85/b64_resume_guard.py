"""Fail-closed source-bound B64 population continuation.
Preflight verifies immutable inputs, then builds pinned geometry locally.
No network, solver launch, parent rewrite or migration occurs in this module.
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
    allowed={'schema','status','mode','admission_id','activation_epoch','expiry_epoch','parent_run','parent_attempt','parent_head','cycle','rng_semantics','baseline_price','baseline_tour_sha256','geometry_sha256','source_files','budget','timing','policy','jobs','parent_roots','private_audit_sha256'}
    require(set(plan)==allowed,'plan field allowlist')
    require(plan.get('schema') == 'gaia-paired-resume-minimal-v1', 'schema')
    require(hexstr(plan['admission_id'],32) and hexstr(plan['private_audit_sha256'],64),'audit reference format')
    require(plan['parent_attempt']==1 and plan['parent_head']=='0235d3a232cb6913e96f879ed7d0f1dc5f2b9618','parent identity')
    require(type(plan['cycle']) is int and plan['cycle']==66,'new cycle')
    require(all(hexstr(plan[k],64) for k in ('baseline_tour_sha256','geometry_sha256')),'geometry digest format')
    require(set(plan['source_files'])=={'e37_paired_resume.py','b64_resume_guard.py','build_g25.py','g24.bin','ab_cap_patch.py'} and all(hexstr(v,64) for v in plan['source_files'].values()),'source allowlist')
    require(plan.get('status') == 'APPROVED_ONE_SHOT', 'inactive plan')
    require(all(type(plan[k]) is int for k in ('activation_epoch','expiry_epoch','parent_run','parent_attempt','baseline_price')),'integer admission fields')
    require(all(type(v) is int for v in plan['budget'].values()) and all(type(v) is int for v in plan['timing'].values()),'integer budget timing')
    mode=plan.get('mode')
    require(mode in ('production','smoke'), 'explicit mode')
    nj,seconds=(20,20700) if mode=='production' else (1,1200)
    require(plan.get('timing') == {'export_reserve':360,'min_search':600,'hardstop_grace':30}, 'timing')
    require(plan.get('budget') == {'jobs':nj,'islands_per_job':4,'np':100,'nk':30,'seconds':seconds,'automatic_repeats':0}, 'budget')
    require(plan.get('parent_run') == 43592577008, 'exact B64 parent')
    require(plan.get('rng_semantics') == 'new-stream-population-continuation', 'RNG semantics')
    require(plan.get('baseline_price') == 288843498, 'baseline')
    require(plan.get('policy') == {'geometry':'paired80k','initialization':'same-ordered-parent-stage-counters-k123-native-late-injection','exchange':'none','restart':'none','operator':'natural','abcap':'single'}, 'policy')
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
    require(isinstance(plan['jobs'],list) and len(plan['jobs'])==nj,'job count')
    require(all(set(j)=={'seed','seeds'} and type(j['seed']) is int and isinstance(j['seeds'],list) for j in plan['jobs']),'job field allowlist')
    jobs=[dict(j,geometry_index=j['seed']%20,pair=(j['seed']%20)//2,arm='shift' if j['seed']%2 else 'control') for j in plan['jobs']]
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
    # Full historical collision audit is private prelaunch, NOT proved by its public SHA reference.
    pairs={}
    for j in jobs:
        require(j['pair']==j['geometry_index']//2 and j['arm']==('shift' if j['geometry_index']%2 else 'control'), 'geometry pair/arm binding')
        pairs.setdefault(j['pair'],[]).append(j['arm'])
    if mode=='production': require(len(pairs)==10 and all(sorted(v)==['control','shift'] for v in pairs.values()), 'pairs')
    require(set(plan['parent_roots'])=={str(x) for x in (range(140,160) if mode=='production' else ids)}, 'parent bank mapping for mode')
    require(all(j['seed'] in range(140,160) for j in jobs), 'same parent job mapping')
    require(all(hexstr(v,64) for v in plan['parent_roots'].values()),'root digest format')
    require(seed in ids, 'unlisted job')
    return dict(plan, job=jobs[ids.index(seed)])


def preflight(driver):
    started=time.time()
    root=Path(driver).resolve().parent
    plan=strict_json((root/'b64_resume_plan.json').read_text())
    admitted=check_plan(plan,os.environ,sys.argv,time.time())
    require(set(plan['source_files'])=={Path(driver).name,'b64_resume_guard.py','build_g25.py','g24.bin','ab_cap_patch.py'}, 'source inventory')
    for name,h in plan['source_files'].items():
        require(digest(root/name)==h, 'source SHA '+name)
    admitted['_parent_records']=validate_parent_files(Path('p'),admitted)
    # r86 also extracts neighbor q; it is deliberately unused, never a donor.
    require(not Path('o').exists(), 'output exists')
    wd=Path('wd')
    require(not wd.exists() or {p.name for p in wd.iterdir()} <= {'a','b'}, 'dirty workdir')
    if os.environ.get('GITHUB_EVENT_PATH'):
        e=json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
        expected={'n':str(plan['budget']['jobs']),'o':str(min(j['seed'] for j in plan['jobs'])),'t':str(plan['budget']['seconds']),'mt':'3000','pert':'25','f':Path(driver).name,'q':f"100,30,{plan['cycle']}",'pr':str(plan['parent_run']),'pb':'0','tl':'0'}
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



def hexstr(value,n):
    return isinstance(value,str) and len(value)==n and all(c in '0123456789abcdef' for c in value)


def read_regular(path):
    import stat
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as f:
        st=os.fstat(f.fileno())
        require(stat.S_ISREG(st.st_mode) and st.st_size<=128*1024*1024,'regular bounded parent file')
        data=f.read(128*1024*1024+1)
        end=os.fstat(f.fileno())
        require(len(data)==st.st_size and (st.st_size,st.st_mtime_ns,st.st_ino)==(end.st_size,end.st_mtime_ns,end.st_ino),'parent file changed')
        return data


def directory_root(folder):
    import re,stat
    folder=Path(folder)
    require(folder.is_dir() and not folder.is_symlink(),'parent directory')
    records=[]
    for p in sorted(folder.iterdir(),key=lambda p:p.name):
        require(re.fullmatch(r'[A-Za-z0-9_.-]{1,128}',p.name) is not None and p.name not in ('.','..'),'parent basename')
        require(len(records)<128,'parent file count')
        data=read_regular(p);records.append([p.name,len(data),hashlib.sha256(data).hexdigest()])
        require(sum(x[1] for x in records)<=512*1024*1024,'parent directory bounds')
    payload=json.dumps(records,ensure_ascii=True,separators=(',',':')).encode('utf-8')
    return hashlib.sha256(b'GAIA_PARENT_DIRECTORY_V1\0'+payload).hexdigest(),{x[0]:(x[1],x[2]) for x in records}


def bound_read(folder,name,records):
    require(name in records,'required parent file')
    raw=read_regular(Path(folder)/name)
    require((len(raw),hashlib.sha256(raw).hexdigest())==records[name],'changed parent member')
    return raw


def validate_parent_files(folder,admitted):
    import gzip
    job=admitted['job'];root,records=directory_root(folder)
    require(root==admitted['parent_roots'][str(job['seed'])],'parent root mismatch')
    required={*(f'c{k}.bin' for k in range(4)),*(f'l{k}_0.txt.gz' for k in range(4)),'s.json','st.json','completion.json','child_exits.json'}
    require(required<=set(records),'required parent files')
    read=lambda name:bound_read(folder,name,records)
    s=json.loads(read('s.json'));st=json.loads(read('st.json'));comp=json.loads(read('completion.json'))
    require(s['runtime_identity']=={'GITHUB_RUN_ID':str(admitted['parent_run']),'GITHUB_RUN_ATTEMPT':str(admitted['parent_attempt']),'GITHUB_SHA':admitted['parent_head']},'parent runtime identity')
    require(s['s']==job['seed'] and s['ri']==job['geometry_index'] and s['cy']==65,'parent mapping')
    require(s['source_kind']=='rng-population-continuation' and s['job_binding']['pair']==job['pair'] and s['job_binding']['arm']==job['arm'],'parent policy pair/arm')
    require(s['parent_run']==43520356668 and hexstr(s['parent_root'],64),'exact B63 ancestry')
    require(not s['runtime_errors'] and s['harvest_allowed'],'parent incomplete')
    exits=s['child_exits']
    require(comp['status']=='COMPLETE_PENDING_INDEPENDENT_AUDIT' and exits==comp['child_exits']==json.loads(read('child_exits.json')),'parent completion')
    require(len(exits)==4 and {e['k'] for e in exits}==set(range(4)) and all(e['rc']==0 and e['trial']==0 for e in exits),'parent exits')
    parentseeds=[st['isl'][str(k)]['seed'] for k in range(4)]
    require(parentseeds==s['job_binding']['seeds'],'parent seed binding')
    current=[x for j in admitted['jobs'] for x in j['seeds']]
    require(not(set(current)&set(parentseeds)) and not({x&65535 for x in current}&{x&65535 for x in parentseeds}),'authenticated parent seed collision')
    for k in range(4):
        require(st['isl'][str(k)]['mode']==('a' if k==0 else 'b') and st['isl'][str(k)]['tr']==0,'parent native initialization')
        require(st['isl'][str(k)]['rng_continuation'] is True,'parent continuation semantics')
        txt=gzip.decompress(read(f'l{k}_0.txt.gz')).decode()
        require(not any(line.startswith('inject ') for line in txt.splitlines()),'parent consumed injection')
    return records


def recheck_parent(admitted,folder):
    root,records=directory_root(folder)
    require(root==admitted['parent_roots'][str(admitted['job']['seed'])] and records==admitted['_parent_records'],'parent changed before launch')


def strict_checkpoint(raw,NN,n,npop=100):
    import io,lzma,numpy as np
    with np.load(io.BytesIO(lzma.decompress(raw)),allow_pickle=False) as z:
        require(set(z.files)=={'a','e','h'},'checkpoint keys')
        a,e,h=z['a'],z['e'],[str(x) for x in z['h']]
    require(a.dtype==np.uint8 and a.shape==(npop,n),'population dimensions')
    require(e.dtype==np.int64 and e.ndim==2 and e.shape[1]==3,'escapes schema')
    require(np.all((a<50)|(a==255)),'rank range')
    require(not e.size or (np.all(e>=0) and np.all(e[:,0]<npop) and np.all(e[:,1:]<n)),'escape range')
    require(np.array_equal(np.sort(e[:,0]*n+e[:,1]),np.flatnonzero(a.ravel()==255)),'exact escape coverage')
    require(len(h)==10 and h[-1]=='deadline' and int(h[1])==1 and int(h[2])==1 and int(h[8])==npop,'Stage1 deadline only; never done/reset')
    require(all(str(int(x))==x for x in h[:9]) and all(int(h[i])>=0 for i in (0,3,4,5,6)),'header counters')
    out=[];ordered=hashlib.sha256()
    for j in range(npop):
        nxt=NN[np.arange(n),np.minimum(a[j],49)].copy();ex=e[e[:,0]==j];nxt[ex[:,1]]=ex[:,2]
        require(np.array_equal(np.sort(nxt),np.arange(n)),'successor permutation')
        seq=[0]*n;sl=nxt.tolist();v=0
        for i in range(n):seq[i]=v;v=sl[v]
        require(v==0 and len(set(seq))==n,'single cycle')
        tour=np.asarray(seq,dtype='<i4');ordered.update(tour.tobytes());out.append(tour)
    return h,out,ordered.hexdigest()


def validate_parents(admitted,folder,NN,n,fkey,cost,ref,local_to_global):
    import numpy as np
    require(n==80000,'same 80k only')
    records=admitted['_parent_records'];result=[]
    for k in range(4):
        raw=bound_read(folder,f'c{k}.bin',records)
        h,ps,ordered=strict_checkpoint(raw,NN,n)
        vals=[cost(t) for t in ps]
        require(all(v is not None and np.isfinite(v) for v in vals),'fixed edge loss')
        # Root-authenticated exact bytes preserve ordered population and ALL header fields.
        # Historical ordered costs/identities remain in private prelaunch audit only.
        result.append((h,ps,None))
    return result


def strict_json(raw):
    def unique(pairs):
        obj={}
        for key,value in pairs:
            require(key not in obj,'duplicate JSON field')
            obj[key]=value
        return obj
    def bad(value):
        raise ValueError('nonfinite JSON')
    return json.loads(raw,object_pairs_hook=unique,parse_constant=bad)
