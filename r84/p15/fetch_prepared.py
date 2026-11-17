"""Read-only validation of frozen prepared packs; no transformations/solver."""
import argparse,hashlib,json,os,shutil,sys,subprocess
from pathlib import Path
from common import *
def lineage():
 cfg=read('config.json');p=cfg.get('prepared_source')
 if p:
  r=api(f'repos/{REPO}/actions/runs/{p["run_id"]}')
  need((r['head_sha'],r['run_attempt'],r['status'],r['conclusion'])==(p['head_sha'],1,'completed','success'),'prepared source not complete success')
  a=read('admission.json');need(a['production_review']['fire_run']==p['run_id'],'prep/fire run mismatch')
  return p['run_id'],p['head_sha']
 return int(os.environ['GITHUB_RUN_ID']),os.environ['GITHUB_SHA']
def fetch(block,arm,dest,cache):
 cfg=read('config.json');run,head=lineage();record=prepared_record(block,arm,run,head);cache.mkdir(parents=True,exist_ok=True)
 z=cache/f'{block}-{arm}.zip';t=z.with_suffix('.bin');artifact_download(record,z,run,head);get_tar(z,t)
 expected=cfg['expected'][f'{block}:{arm}'];pins=dict(expected['members']);b=expected['manifest_text'].encode();pins['manifest.json']={'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)};unpack_pinned(t,dest,pins)
 return record
def main():
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=['barrier','fire','production'],required=True);p.add_argument('--index',type=int,default=0);a=p.parse_args();source_gate();active_gate();cfg=read('config.json');Path('o').mkdir(exist_ok=True)
 if a.mode=='barrier':
  need(cfg.get('prepared_source') is not None,'production lineage missing');records={}
  for b in range(4):
   for arm in 'abcde':
    d=Path('wd/check')/f'{b}-{arm}';records[f'{b}:{arm}']=fetch(b,arm,d,Path('wd/cache'));shutil.rmtree(d)
  Path('o/VALIDATION.json').write_text(json.dumps(records,indent=2)+'\n');return
 fire=a.mode=='fire';need(fire==(cfg.get('prepared_source') is None),'phase mismatch')
 selected=cfg['fire_select'] if fire else [[a.index//5,'abcde'[a.index%5],w] for w in range(4)]
 cache=Path('wd/cache');downloaded=set();records={}
 for b,arm,w in selected:
  key=(b,arm)
  if key not in downloaded:records[f'{b}:{arm}']=fetch(b,arm,Path('wd/packs')/f'{b}-{arm}',cache);downloaded.add(key)
 for w,(b,arm,source_w) in enumerate(selected):
  dest=Path('wd/inputs')/str(a.index)/str(w);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(Path('wd/packs')/f'{b}-{arm}'/f'{source_w:02d}',dest)
 rows=[]
 for i in range(20):
  row=[]
  for w in range(4):
   b,arm,sw=selected[w] if fire and i==0 else (i//5,'abcde'[i%5],w)
   row.append({'bundle':str((Path('wd/inputs')/str(i)/str(w)).resolve()),'seed':cfg['fire_seeds' if fire else 'seeds'][i][w],'context_sha256':cfg['expected'][f'{b}:{arm}']['members'][f'{sw:02d}/context.json']['sha256']})
  rows.append(row)
 Path('wd/assignments.json').write_text(json.dumps(rows,indent=2)+'\n');Path('o/INPUTS.json').write_text(json.dumps(records,indent=2)+'\n')
 if not fire:need(sha('wd/assignments.json')==read('admission.json')['assignments_sha256'],'frozen assignment checksum')
if __name__=='__main__':main()
