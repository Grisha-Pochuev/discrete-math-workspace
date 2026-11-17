import hashlib,json,os,subprocess,time,tarfile,zipfile,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent
REPO='Grisha-Pochuev/discrete-math-workspace'
def need(x,m):
 if not x:raise ValueError(m)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def read(n):return json.loads((ROOT/n).read_text())
def api(ep):return json.loads(subprocess.check_output(['gh','api',ep],timeout=60))
def source_gate():
 for n,h in read('sources.json')['text_sources'].items():need(sha(ROOT/n)==h,'source pin '+n)
 need(os.environ['GITHUB_REPOSITORY']==REPO and os.environ['GITHUB_RUN_ATTEMPT']=='1','run scope')
 a=read('admission.json');need(a['status']=='APPROVED_ONE_SHOT' and a['activation_epoch']<=time.time()<a['expiry_epoch'],'admission window')
 return a
def active_gate():
 own=int(os.environ['GITHUB_RUN_ID'])
 for status in ('in_progress','queued','waiting','requested','pending'):
  payload=json.loads(subprocess.check_output(['gh','api','--paginate','--slurp',f'repos/{REPO}/actions/runs?status={status}&per_page=100'],timeout=90))
  need(not any(r['id']!=own for p in payload for r in p['workflow_runs']),'other active run')
 history=api(f'repos/{REPO}/actions/runs?head_sha='+os.environ['GITHUB_SHA']+'&per_page=100');need(history['total_count']<=100,'history truncated')
 path=os.environ['WORKFLOW_PATH'];need(not any(r['id']!=own and r['path']==path for r in history['workflow_runs']),'one dispatch per head')
def artifact_download(record,dest,run_id,head):
 ep=f'repos/{REPO}/actions/artifacts/{record["id"]}';m=api(ep)
 for key in ('id','name','size_in_bytes','digest'):need(m[key]==record[key],'artifact '+key)
 need(not m['expired'] and m['workflow_run']['id']==run_id and m['workflow_run']['head_sha']==head,'artifact lineage')
 dest=Path(dest);dest.parent.mkdir(parents=True,exist_ok=True)
 with dest.open('xb') as f:subprocess.run(['gh','api',ep+'/zip'],stdout=f,check=True,timeout=300)
 need(dest.stat().st_size==m['size_in_bytes'] and sha(dest)==m['digest'].split(':')[-1],'artifact byte identity')
 return m
def get_tar(zip_path,out):
 with zipfile.ZipFile(zip_path) as z:
  need(z.namelist()==['result.bin'] and z.getinfo('result.bin').file_size<2*1024**3,'ZIP members/bounds');need(z.testzip() is None,'ZIP CRC')
  with z.open('result.bin') as i,Path(out).open('xb') as o:shutil.copyfileobj(i,o)
def unpack_pinned(tar_path,dest,pins):
 dest=Path(dest);dest.mkdir(parents=True,exist_ok=True)
 with tarfile.open(tar_path,'r:xz') as t:
  members=t.getmembers();need(len(members)<30000 and sum(m.size for m in members)<8*1024**3,'tar bounds');need(len({m.name for m in members})==len(members),'duplicate tar member');by={m.name:m for m in members}
  for name,rec in pins.items():
   p=Path(name);need(not p.is_absolute() and '..' not in p.parts,'unsafe name');m=by[name];need(m.isfile() and m.size==rec['bytes'],'member shape');target=dest/p;target.parent.mkdir(parents=True,exist_ok=True)
   with t.extractfile(m) as i,target.open('xb') as o:shutil.copyfileobj(i,o)
   need(sha(target)==rec['sha256'],'member checksum '+name)
def prepared_record(block,arm,source_run,source_head):
 cfg=read('config.json');name=f'q-{source_run}-{block}-{arm}'
 p=api(f'repos/{REPO}/actions/runs/{source_run}/artifacts?per_page=100');need(p['total_count']==len(p['artifacts']),'artifacts truncated')
 hits=[x for x in p['artifacts'] if x['name']==name];need(len(hits)==1,'missing/duplicate prepared input');rec=hits[0]
 if cfg.get('prepared_source'):
  frozen=cfg['prepared_source']['artifacts'][f'{block}:{arm}']
  for k in ('id','name','size_in_bytes','digest'):need(rec[k]==frozen[k],'frozen prepared identity')
 need(rec['workflow_run']['id']==source_run and rec['workflow_run']['head_sha']==source_head and not rec['expired'],'prepared lineage')
 return rec
