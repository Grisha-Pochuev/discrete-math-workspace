"""Pinned input-only transformations; this module does not run a solver."""
import argparse,sys,gzip,json,shutil,time,tarfile,subprocess
from pathlib import Path
import numpy as np
from common import *
def prepare(block,source,work):
 cfg=read('config.json');job=cfg['blocks'][block];peer=2 if job==0 else 0 if job==2 else 14 if job==12 else 12
 work=Path(work);work.mkdir(parents=True,exist_ok=False);collection=work/'collection';collection.mkdir();(collection/'audits').mkdir()
 for j in (job,peer):
  row=cfg['parents'][str(j)];z=work/f'p{j}.zip';artifact_download(row['artifact'],z,cfg['parent_run'],cfg['parent_head']);t=work/f'p{j}.bin';get_tar(z,t);unpack_pinned(t,collection/'unpacked'/str(j),row['members'])
  (collection/'audits'/f'{j}.json').write_text(json.dumps(row['audit'])+'\n')
 (collection/'RESIDUAL_SUPPORT.json').write_text(json.dumps(cfg['residual'])+'\n')
 g=work/'global';g.mkdir()
 for name,key in [('a','coordinates_sha256'),('b','reference_sha256')]:
  subprocess.run(['curl','--fail','--location','--max-time','300','--max-filesize','60000000','--output',str(g/name),f'https://raw.githubusercontent.com/{REPO}/inp/w_{name}.bin'],check=True,timeout=310);need(sha(g/name)==cfg['global'][key],'global pin')
 sys.path[:0]=[str(Path(source)/'engine'),str(ROOT)];import region_tools as rt,shift_materializer as sm,materialize as dm,export as de
 x=np.loadtxt(gzip.open(g/'a','rt'),dtype='f8');r=np.loadtxt(gzip.open(g/'b','rt'),dtype='i8')-1;delta=read('delta.json');r=rt.apply_edges(r,delta['removed'],delta['added']);r=np.roll(r,-int(np.flatnonzero(r==delta['start'])[0]))
 if r[1]!=delta['second']:r=np.r_[r[:1],r[:0:-1]]
 need(r[1]==delta['second'] and rt.metric(x,r)==288843498,'reference');np.save(g/'x.npy',x);np.save(g/'r.npy',r)
 selection=cfg['selection'][str(job)];sm.prepare_job(job,collection,g,work/'shift',rt,selection['core'],selection['selection_config'])
 (work/'diversity').mkdir();dm.configure(collection,g,work/'diversity',cfg['union_hashes'])
 for w in range(4):de.freeze(job,w)
 for arm in ('a','b','c','d','e'):
  dest=Path('o/prepared')/arm;dest.mkdir(parents=True,exist_ok=False);expected=cfg['expected'][f'{block}:{arm}']
  for w in range(4):
   src=work/'shift'/f'shift{0 if arm=="b" else 1}'/f'{w:02d}' if arm in ('b','c') else work/'diversity/bundles'/f"j{job}_w{w}_{ {'a':'control','d':'mild','e':'strong'}[arm]}"
   target=dest/f'{w:02d}';shutil.copytree(src,target)
  for name,rec in expected['members'].items():need(sha(dest/name)==rec['sha256'] and (dest/name).stat().st_size==rec['bytes'],'frozen output '+name)
  (dest/'manifest.json').write_text(expected['manifest_text'])
  out=Path('o/archives')/arm;out.mkdir(parents=True)
  with tarfile.open(out/'result.bin','w:xz',preset=1) as t:
   for name in sorted(expected['members']):t.add(dest/name,arcname=name,recursive=False)
   t.add(dest/'manifest.json',arcname='manifest.json',recursive=False)
 return {'block':block,'source_job':job,'status':'FIVE_FROZEN_ARMS_PASS','search_started':False}
def main():
 a=argparse.ArgumentParser();a.add_argument('--block',type=int,required=True);a.add_argument('--source',required=True);a.add_argument('--work',required=True);v=a.parse_args();source_gate();active_gate();t=time.monotonic();out=prepare(v.block,v.source,v.work);out['seconds']=time.monotonic()-t;Path('o/PREPARATION.json').write_text(json.dumps(out,indent=2)+'\n')
if __name__=='__main__':main()
