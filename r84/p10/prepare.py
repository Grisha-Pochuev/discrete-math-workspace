"""Pinned inputs to nested numerical instance; no search."""
import argparse,gzip,hashlib,json,shutil,subprocess,sys,tarfile,zipfile
from pathlib import Path
import numpy as np

def need(x,m):
 if not x:raise ValueError(m)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser()
 for k in ('source-root','inputs','output'):p.add_argument('--'+k,type=Path,required=True)
 p.add_argument('--index',type=int,required=True)
 a=p.parse_args();root=Path(__file__).resolve().parent;allc=json.loads((root/'parents.json').read_text());need(0<=a.index<20,'index');job=allc['jobs'][a.index];c=dict(allc['common'],**allc['parents'][job['center']]);pins=json.loads((root/'sources.json').read_text())
 for n,h in pins['text_sources'].items():need(sha(root/n)==h,'source pin '+n)
 need(not a.output.exists(),'fresh output');a.output.mkdir(parents=True)
 need(sha(a.inputs/'parent.zip')==c['artifact']['digest'].split(':')[1],'zip SHA')
 b=a.output/'parent80';b.mkdir()
 with zipfile.ZipFile(a.inputs/'parent.zip') as z:
  need(z.namelist()==['result.bin'] and z.getinfo('result.bin').file_size<512*1024**2,'zip bounds');need(z.testzip() is None,'CRC');z.extract('result.bin',a.output)
 with tarfile.open(a.output/'result.bin','r:xz') as t:
  mm=t.getmembers();need(len(mm)<2000 and sum(x.size for x in mm)<1024**3,'tar bounds');need(len({x.name for x in mm})==len(mm),'duplicates');by={x.name:x for x in mm}
  for n,s in c['members'].items():
   x=by[n];need(x.isfile() and '..' not in Path(n).parts and not Path(n).is_absolute() and x.size==s['bytes'],'member');data=t.extractfile(x).read();need(hashlib.sha256(data).hexdigest()==s['sha256'],'member hash');need(s['target'] in ('instance.bin','vertices.npy','base.txt','checkpoint.txt'),'target');(b/s['target']).write_bytes(data)
 (b/'context.json').write_text(c['context_text']);need(sha(b/'context.json')==c['context_sha256'],'context')
 sys.path.insert(0,str(a.source_root/'engine'));sys.path.insert(0,str(root));import region_tools as rt
 for name,k in [('a','coordinates_sha256'),('b','reference_sha256')]:need(sha(a.inputs/name)==c[k],'numerical pin')
 x=np.loadtxt(gzip.open(a.inputs/'a','rt'),dtype='f8');r=np.loadtxt(gzip.open(a.inputs/'b','rt'),dtype='i8')-1
 d=json.loads((root/'delta.json').read_text());r=rt.apply_edges(r,d['removed'],d['added']);r=np.roll(r,-int(np.flatnonzero(r==d['start'])[0]))
 if r[1]!=d['second']:r=np.concatenate((r[:1],r[:0:-1]))
 need(r[1]==d['second'],'orientation');np.save(a.output/'x.npy',x);np.save(a.output/'r.npy',r)
 m,inst,h,pop,vals,base,ref,*_=rt.bind_global(b,x,r);need([int(v-ref) for v in vals]==c['gaps'],'gaps');need(rt.metric(x,r)==m['global_binding']['reference_cost'],'full reference cost')
 rt.expand_region(b,a.output/'x.npy',a.output/'r.npy',a.output/'expanded150',150000)
 need(sha(a.output/'expanded150/context.json')==c['expanded_context_sha256'],'deterministic expanded context')
 # Recompute global changed edges independently of the lift loop.
 m,inst,h,pop,vals,base,ref=rt.engine.admit(a.output/'expanded150',wide=True);v=np.load(a.output/'expanded150/vertices.npy');N=len(r)
 def edges(t):
  u=v[t];w=np.roll(u,-1);return np.sort(np.minimum(u,w)*N+np.maximum(u,w))
 be=edges(base)
 for i,t in enumerate(pop):
  e=edges(t);removed=np.setdiff1d(be,e,assume_unique=True);added=np.setdiff1d(e,be,assume_unique=True);hh=hashlib.sha256(removed.astype('<i8').tobytes()+b'ADDED'+added.astype('<i8').tobytes()).hexdigest();need(hh==c['global_delta_hashes'][i],'global route changed')
 need([int(v-ref) for v in vals]==c['gaps'],'expanded gaps')
 need(sha(a.source_root/'run_experiment.py')==pins['original_runner_sha256'],'runner pin');shutil.copyfile(root/'run_experiment.py',a.source_root/'run_experiment.py')
 subprocess.run([sys.executable,str(a.source_root/'engine/build_kernel.py'),'--output',str(a.output/'k'),'--compact','--wide','--objective64'],check=True)
 (a.output/'PREPARATION.json').write_text(json.dumps({'status':'ALL100_GLOBAL_ROUTES_PRESERVED','context_sha256':c['expanded_context_sha256'],'routes':100,'search_started':False})+'\n')
if __name__=='__main__':main()
