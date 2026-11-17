"""Pinned parent fetch and lossless import only; never invokes a solver."""
import argparse,json,shutil,sys,tarfile,zipfile
from pathlib import Path
from common import *
from materialize import materialize

def main():
 p=argparse.ArgumentParser();p.add_argument('--block',type=int,choices=(0,1),required=True);a=p.parse_args();source_gate();active_gate();cfg=read('config.json');record=cfg['parents'][str(a.block)];job=record['job'];run=api(f'repos/{REPO}/actions/runs/44016972185')
 need((run['head_sha'],run['run_attempt'],run['status'],run['conclusion'])==(cfg['parent_head'],1,'completed','success'),'parent run')
 root=Path('wd/parent');root.mkdir(parents=True,exist_ok=False);z=root/'original.zip';artifact_download(record['artifact'],z,44016972185,cfg['parent_head'])
 pins=record['members'];seen=set();total=0;names=set()
 with zipfile.ZipFile(z) as zipf:
  need(zipf.namelist()==['result.bin'] and zipf.getinfo('result.bin').file_size<2*1024**3,'ZIP bounds');need(zipf.testzip() is None,'ZIP CRC')
  with zipf.open('result.bin') as stream,tarfile.open(fileobj=stream,mode='r|xz') as t:
   for member in t:
    total+=member.size;need(total<2*1024**3 and len(names)<30000,'tar bounds');need(member.name not in names,'duplicate tar member');names.add(member.name)
    if member.name not in pins:continue
    pin=pins[member.name];need(member.isfile() and member.size==pin['bytes'],'member shape');relative=Path(member.name).relative_to('o/run');need('..' not in relative.parts,'member path');dest=root/relative;dest.parent.mkdir(parents=True,exist_ok=True)
    with t.extractfile(member) as i,dest.open('xb') as o:shutil.copyfileobj(i,o)
    need(sha(dest)==pin['sha256'],'parent member hash');seen.add(member.name)
 need(seen==set(pins),'missing parent files')
 for arm in ('initial','final'):
  dest=Path('wd/packs')/f'{a.block}-{arm}';receipts=[]
  for w in range(4):receipts.append(materialize(root/f'{w:02d}',dest/f'{w:02d}',Path('wd/s'),job,w,arm,ROOT/f'audit_{job}.json'))
  expected=cfg['expected'][f'{a.block}:{arm}']
  for n,pin in expected['members'].items():need(sha(dest/n)==pin['sha256'] and (dest/n).stat().st_size==pin['bytes'],'prepared bytes differ')
  (dest/'manifest.json').write_text(expected['manifest_text'])
  out=Path('o/prepared')/arm;out.mkdir(parents=True)
  with tarfile.open(out/'result.bin','w:xz') as t:
   for f in sorted(dest.rglob('*')):
    if f.is_file():t.add(f,arcname=str(f.relative_to(dest)),recursive=False)
  (Path('o')/f'PREPARE-{arm}.json').write_text(json.dumps(receipts,indent=2)+'\n')
if __name__=='__main__':main()
