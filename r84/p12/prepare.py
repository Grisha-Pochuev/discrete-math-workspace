"""Exact continuation materialization and build; no search or network."""
import argparse,hashlib,json,shutil,subprocess,sys,tarfile,zipfile
from pathlib import Path
import numpy as np

def need(ok,message):
    if not ok: raise ValueError(message)

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def materialize(archive,output,parent,source):
    archive,output,source=map(Path,(archive,output,source))
    need(not output.exists(),'fresh output required')
    need(archive.stat().st_size==parent['artifact']['size_in_bytes'],'ZIP size')
    need(sha(archive)==parent['artifact']['digest'].split(':')[1],'ZIP SHA')
    output.mkdir(parents=True)
    with zipfile.ZipFile(archive) as z:
        need(z.namelist()==['result.bin'],'ZIP members')
        need(z.getinfo('result.bin').file_size<256*1024**2,'ZIP unpack bounds')
        need(z.testzip() is None,'ZIP CRC')
        with z.open('result.bin') as stream, (output/'result.bin').open('xb') as out: shutil.copyfileobj(stream,out)
    bundle=output/'parent';bundle.mkdir()
    with tarfile.open(output/'result.bin','r:xz') as t:
        members=t.getmembers()
        need(len(members)<3000 and sum(x.size for x in members)<2*1024**3,'tar bounds')
        need(len({x.name for x in members})==len(members),'duplicate tar members')
        for x in members:
            need(not Path(x.name).is_absolute() and '..' not in Path(x.name).parts and (x.isfile() or x.isdir()),'unsafe tar member')
        by={x.name:x for x in members};targets=set()
        for name,record in parent['members'].items():
            x=by[name];target=record['target']
            need(x.isfile() and x.size==record['bytes'],'member size/type')
            need(target in ('instance.bin','vertices.npy','base.txt','checkpoint.txt') and target not in targets,'target')
            targets.add(target)
            with t.extractfile(x) as stream,(bundle/target).open('xb') as out: shutil.copyfileobj(stream,out)
            need(sha(bundle/target)==record['sha256'],'member SHA')
        need(len(targets)==4,'incomplete population bundle')
    (bundle/'context.json').write_text(parent['context_text'])
    need(sha(bundle/'context.json')==parent['context_sha256'],'context SHA')
    sys.path.insert(0,str(source/'engine'))
    import paired_engine as engine
    manifest,inst,header,population,values,base,ref=engine.admit(bundle,wide=True)
    need(inst.n==parent['vertices'] and manifest['population']==100 and len(population)==100,'population dimensions')
    need(header[2:4]==['2','2'] and int(header[1])==parent['generation'] and int(header[7])==parent['children'],'counter/operator preservation')
    need(hashlib.sha256(np.asarray(population,dtype='<i8').tobytes()).hexdigest()==parent['ordered_population_sha256']==manifest['ordered_population_sha256'],'ordered population identity')
    need([int(v-ref) for v in values]==parent['gaps'],'all100 exact gaps')
    need(manifest['source_run']=='43885175878' and manifest['source_slot']==f"job{parent['index']}/2",'source identity')
    proof=manifest['identity_evidence']
    need(proof['source_context_sha256']==parent['source_context_sha256'] and proof['source_checkpoint_sha256']==manifest['files']['checkpoint']['sha256'],'source proof')
    receipt={'status':'ALL100_EXACT_CONTINUATION_PASS','index':parent['index'],'vertices':inst.n,'context_sha256':parent['context_sha256'],'ordered_population_sha256':parent['ordered_population_sha256'],'generation':int(header[1]),'children':int(header[7]),'routes':100,'gaps':parent['gaps'],'search_started':False,'geometry_unchanged':True,'rng_state_restored':False}
    (output/'PREPARATION.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt

def main():
    p=argparse.ArgumentParser()
    for k in ('source-root','inputs','output'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--index',type=int,required=True);a=p.parse_args();root=Path(__file__).resolve().parent
    config=json.loads((root/'parents.json').read_text());pins=json.loads((root/'sources.json').read_text())
    need(config['parent_run']==43885175878 and config['parent_attempt']==1 and config['parent_head']=='7d1d7de56fd31f2d0c1685d690f1ffa9dd67ae8d','source binding')
    need(0<=a.index<20 and len(config['parents'])==20,'index')
    for name,digest in pins['text_sources'].items():need(sha(root/name)==digest,'source pin '+name)
    parent=config['parents'][a.index];need(parent['index']==a.index,'parent index')
    materialize(a.inputs/'parent.zip',a.output,parent,a.source_root)
    need(sha(a.source_root/'run_experiment.py')==pins['original_runner_sha256'],'original runner pin')
    shutil.copyfile(root/'run_experiment.py',a.source_root/'run_experiment.py')
    subprocess.run([sys.executable,str(a.source_root/'engine/build_kernel.py'),'--output',str(a.output/'k'),'--compact','--wide','--objective64'],check=True)

if __name__=='__main__':main()
