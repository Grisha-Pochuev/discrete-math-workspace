"""Read pinned artifact members and prepare an audited explicit population."""
import argparse,hashlib,json,shutil,subprocess,sys,tarfile,zipfile
from pathlib import Path

def need(x,m):
    if not x:raise ValueError(m)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser()
    for k in ('source-root','parent','output'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--index',type=int,required=True);a=p.parse_args();root=Path(__file__).resolve().parent
    need(0<=a.index<20,'index');conf=json.loads((root/'sources.json').read_text()); row=json.loads((root/'parents.json').read_text())['parents'][a.index]
    for n,h in conf['text_sources'].items():need(sha(root/n)==h,'source hash '+n)
    need(sha(a.parent)==row['zip_sha256'],'artifact ZIP'); need(not a.output.exists(),'fresh output');a.output.mkdir(parents=True)
    with zipfile.ZipFile(a.parent) as z:
        need(z.namelist()==['result.bin'] and z.getinfo('result.bin').file_size<512*1024**2,'ZIP bounds')
        need(z.testzip() is None,'CRC');z.extract('result.bin',a.output)
    bundle=a.output/'c';bundle.mkdir()
    with tarfile.open(a.output/'result.bin','r:xz') as t:
        members=t.getmembers();need(len(members)<2000 and sum(m.size for m in members)<1024**3,'tar bounds')
        need(len({m.name for m in members})==len(members),'duplicate members')
        by={m.name:m for m in members}
        for name,spec in row['members'].items():
            need(spec['target'] in ('instance.bin','vertices.npy','base.txt','checkpoint.txt'),'target allowlist')
            m=by[name];need(m.isfile() and not Path(name).is_absolute() and '..' not in Path(name).parts,'regular safe member')
            data=t.extractfile(m).read();need(hashlib.sha256(data).hexdigest()==spec['sha256'],'member hash '+name)
            (bundle/spec['target']).write_bytes(data)
    (bundle/'context.json').write_text(row['context_text']);need(sha(bundle/'context.json')==row['context_sha256'],'new context')
    sys.path.insert(0,str(a.source_root/'engine'));import paired_engine as engine
    _,_,hdr,pop,vals,base,ref=engine.admit(bundle,wide=True)
    import numpy as np
    need(hashlib.sha256(b''.join(t.astype('<i8').tobytes() for t in pop)).hexdigest()==row['ordered_population_sha256'],'ordered100')
    need([int(v)-ref for v in vals]==row['gaps'] and hdr[2]==hdr[3]=='2','audited100 gaps')
    # Introduce exactly one known reference, preserving 99 ordered parents.
    need(not any(engine.edgekey(t)==engine.edgekey(base) for t in pop),'control unexpectedly contains reference')
    slot=max(range(100),key=lambda i:(vals[i],-i))
    tdir=a.output/'t';shutil.copytree(bundle,tdir)
    tpop=list(pop);tvals=list(vals);tpop[slot]=base.copy();tvals[slot]=ref
    engine.write_checkpoint(tdir/'checkpoint.txt',hdr,tpop,tvals)
    m=json.loads((tdir/'context.json').read_text())
    m['files']['checkpoint']['sha256']=sha(tdir/'checkpoint.txt')
    m['ordered_population_sha256']=hashlib.sha256(b''.join(t.astype('<i8').tobytes() for t in tpop)).hexdigest()
    m['identity_evidence']={'kind':'one-reference-replacement','parent_context_sha256':row['context_sha256'],'replaced_index':slot,'retained_ordered_parents':99,'native_nn_identity_claimed':True,'rng_state_restored':False}
    (tdir/'context.json').write_text(json.dumps(m,sort_keys=True,separators=(',',':')))
    _,_,th,tp,tv,tbase,tref=engine.admit(tdir,wide=True)
    need(th==hdr and tref==ref and tv==tvals,'treatment readback')
    need(all(np.array_equal(tp[i],pop[i]) for i in range(100) if i!=slot),'retained99')
    need(sum(engine.edgekey(t)==engine.edgekey(base) for t in tp)==1,'one reference')
    need(sha(a.source_root/'run_experiment.py')==conf['original_runner_sha256'],'original runner pin')
    shutil.copyfile(root/'run_experiment.py',a.source_root/'run_experiment.py')
    subprocess.run([sys.executable,str(a.source_root/'engine/build_kernel.py'),'--output',str(a.output/'k'),'--compact','--wide','--objective64'],check=True)
    (a.output/'PREPARATION.json').write_text(json.dumps({'status':'AUDITED100_CHECKPOINT_IMPORT_PASS','routes':100,'context_sha256':row['context_sha256'],'checkpoint_sha256':sha(bundle/'checkpoint.txt'),'treatment_context_sha256':sha(tdir/'context.json'),'replaced_index':slot,'retained':99,'external_preparation_injection':True,'injected_zero_is_not_improvement':True,'old_tour_sha256':hashlib.sha256(pop[slot].astype('<i8').tobytes()).hexdigest(),'new_tour_sha256':hashlib.sha256(base.astype('<i8').tobytes()).hexdigest(),'control_initial_mean_gap':sum(vals)/100-ref,'treatment_initial_mean_gap':sum(tvals)/100-ref,'search_started':False},indent=2)+'\n')
if __name__=='__main__':main()
