"""Read-only frozen prepared inputs; no solver and no transformations."""
import argparse,hashlib,json,os,shutil
from pathlib import Path
from common import *
def lineage():
 cfg=read('config.json');p=cfg.get('prepared_source')
 if p:
  r=api(f'repos/{REPO}/actions/runs/{p["run_id"]}');need((r['head_sha'],r['run_attempt'],r['status'],r['conclusion'])==(p['head_sha'],1,'completed','success'),'prepared source success')
  need(read('admission.json')['production_review']['fire_run']==p['run_id'],'fire/prep lineage');return p['run_id'],p['head_sha']
 return int(os.environ['GITHUB_RUN_ID']),os.environ['GITHUB_SHA']
def fetch(block,arm,dest,cache):
 cfg=read('config.json');run,head=lineage();record=prepared_record(block,arm,run,head);cache.mkdir(parents=True,exist_ok=True);z=cache/f'{block}-{arm}.zip';t=z.with_suffix('.bin');artifact_download(record,z,run,head);get_tar(z,t)
 expected=cfg['expected'][f'{block}:{arm}'];pins=dict(expected['members']);b=expected['manifest_text'].encode();pins['manifest.json']={'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)};unpack_pinned(t,dest,pins);return record

def assignment(i,w,fire=False):
 cfg=read('config.json')
 if fire:b,arm,sw=cfg['fire_select'][w]
 else:b,arm,sw=i//10,('initial' if i%2==0 else 'final'),w
 return {'bundle':str((Path('wd/inputs')/str(i)/str(w)).resolve()),'seed':cfg['fire_seeds'][w] if fire else cfg['seeds'][i][w],'context_sha256':cfg['expected'][f'{b}:{arm}']['members'][f'{sw:02d}/context.json']['sha256'],'source_job':cfg['blocks'][b],'arm':arm}
def main():
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=['barrier','fire','production'],required=True);p.add_argument('--index',type=int,default=0);a=p.parse_args();source_gate();active_gate();cfg=read('config.json');Path('o').mkdir(exist_ok=True)
 if a.mode=='barrier':
  need(cfg.get('prepared_source') is not None,'missing production lineage');records={}
  for b in range(2):
   for arm in ('initial','final'):
    d=Path('wd/check')/f'{b}-{arm}';records[f'{b}:{arm}']=fetch(b,arm,d,Path('wd/cache'));shutil.rmtree(d)
  Path('o/VALIDATION.json').write_text(json.dumps(records,indent=2)+'\n');return
 fire=a.mode=='fire';need(fire==(cfg.get('prepared_source') is None),'phase mismatch');need(0<=a.index<20 and (not fire or a.index==0),'index')
 selected=cfg['fire_select'] if fire else [[a.index//10,('initial' if a.index%2==0 else 'final'),w] for w in range(4)]
 records={}
 for b,arm,sw in selected:
  key=f'{b}:{arm}'
  if key not in records:records[key]=fetch(b,arm,Path('wd/packs')/f'{b}-{arm}',Path('wd/cache'))
 for w,(b,arm,sw) in enumerate(selected):
  dest=Path('wd/inputs')/str(a.index)/str(w);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(Path('wd/packs')/f'{b}-{arm}'/f'{sw:02d}',dest)
 rows=[assignment(0,w,True) for w in range(4)] if fire else [[assignment(i,w) for w in range(4)] for i in range(20)]
 Path('wd/assignments.json').write_text(json.dumps(rows,indent=2)+'\n');Path('o/INPUTS.json').write_text(json.dumps(records,indent=2)+'\n')
 if not fire:need(sha('wd/assignments.json')==read('admission.json')['assignments_sha256'],'assignment freeze')
if __name__=='__main__':main()
