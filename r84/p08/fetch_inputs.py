"""Retrieve one pinned existing artifact; no new computation."""
import argparse,json,hashlib,os,subprocess,time
from pathlib import Path
def need(x,m):
    if not x:raise ValueError(m)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--job-index',type=int,required=True);a=p.parse_args();root=Path(__file__).resolve().parent
    c=json.loads((root/'sources.json').read_text())
    for n,h in c['text_sources'].items():need(sha(root/n)==h,'source pin '+n)
    ad=json.loads((root/'admission.json').read_text());need(0<=a.job_index<20,'index');j=ad['jobs'][a.job_index];r=json.loads((root/'parents.json').read_text())['parents'][a.job_index];need(j['i']==r['i']==a.job_index,'matrix')
    need(ad['status']=='APPROVED_ONE_SHOT' and ad['activation_epoch']<=time.time()<ad['expiry_epoch'],'admission')
    need(os.environ['GITHUB_RUN_ATTEMPT']=='1' and os.environ['GITHUB_REPOSITORY']=='Grisha-Pochuev/discrete-math-workspace','runtime identity')
    need(not a.output.exists(),'fresh output');a.output.mkdir(parents=True)
    ep='repos/'+os.environ['GITHUB_REPOSITORY']+'/actions/artifacts/'+str(r['artifact_id']);meta=json.loads(subprocess.check_output(['gh','api',ep],timeout=60))
    need(not meta['expired'] and meta['name']==r['artifact_name'] and meta['size_in_bytes']==r['artifact_bytes'] and meta['digest']=='sha256:'+r['zip_sha256'],'artifact metadata')
    need(meta['workflow_run']['id']==r['parent_run'] and meta['workflow_run']['head_sha']==r['parent_head'],'source run')
    target=a.output/'parent.zip'
    with target.open('xb') as f:subprocess.run(['gh','api',ep+'/zip'],stdout=f,check=True,timeout=180)
    need(target.stat().st_size==r['artifact_bytes'] and sha(target)==r['zip_sha256'],'artifact bytes')
    (a.output/'RECEIPT.json').write_text(json.dumps({'artifact':meta,'index':a.job_index,'nonce':ad['nonce'],'search_started':False},indent=2)+'\n')
if __name__=='__main__':main()
