"""Read immutable original inputs for one bounded target test."""
import argparse,hashlib,json,os,subprocess,time
from pathlib import Path
def need(x,m):
    if not x: raise ValueError(m)
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=Path(__file__).resolve().parent
    config=json.loads((root/'sources.json').read_text())
    for name,digest in config['text_sources'].items():need(sha(root/name)==digest,'source pin '+name)
    admission=json.loads((root/'admission.json').read_text());m=json.loads((root/'parents.json').read_text());r=m['parents'][0]
    need(admission['status']=='APPROVED_ONE_SHOT' and admission['activation_epoch']<=time.time()<admission['expiry_epoch'],'admission time')
    need(os.environ['GITHUB_RUN_ATTEMPT']=='1','one attempt');need(os.environ['GITHUB_REPOSITORY']=='Grisha-Pochuev/discrete-math-workspace','repository')
    need(not a.output.exists(),'fresh input directory');a.output.mkdir(parents=True)
    endpoint='repos/'+os.environ['GITHUB_REPOSITORY']+'/actions/artifacts/'+str(admission['artifact_id'])
    meta=json.loads(subprocess.check_output(['gh','api',endpoint],timeout=60));(a.output/'artifact.json').write_text(json.dumps(meta,indent=2)+'\n')
    need(not meta['expired'] and meta['name']=='o'+str(r['slot']) and meta['size_in_bytes']==admission['artifact_bytes'],'artifact metadata')
    need(meta['digest']=='sha256:'+r['zip_sha256'],'artifact digest');need(meta['workflow_run']['id']==m['parent_run'] and meta['workflow_run']['head_sha']==m['parent_head'],'artifact run')
    target=a.output/'parent.zip'
    with target.open('xb') as f: subprocess.run(['gh','api',endpoint+'/zip'],stdout=f,check=True,timeout=180)
    need(target.stat().st_size==admission['artifact_bytes'] and sha(target)==r['zip_sha256'],'original ZIP bytes')
    for name,expected in [('a',m['coordinates_sha256']),('b',m['reference_sha256'])]:
        out=a.output/name
        subprocess.run(['curl','--fail','--location','--max-time','300','--output',str(out),'https://raw.githubusercontent.com/Grisha-Pochuev/discrete-math-workspace/inp/w_'+name+'.bin'],check=True,timeout=310)
        need(sha(out)==expected,'numerical input digest')
    need(time.time()<admission['expiry_epoch'],'admission expired during read')
    Path('o/input-receipt.json').write_text(json.dumps({'status':'ORIGINAL_INPUTS_SHA_SIZE_PASS','artifact_id':meta['id'],'parent_run':m['parent_run'],'head':m['parent_head'],'nonce':admission['nonce'],'search_started':False},indent=2)+'\n')
if __name__=='__main__':main()
