#!/usr/bin/env python3
# compact workflow-run lookup used by the browser-side probe
import json, os, sys, urllib.request

repo=os.environ['GITHUB_REPOSITORY']
tok=os.environ['GITHUB_TOKEN']
workflow=sys.argv[1] if len(sys.argv)>1 else 'e07-d2.yml'
url=f'https://api.github.com/repos/{repo}/actions/workflows/{workflow}/runs?per_page=20'
req=urllib.request.Request(url,headers={
    'Authorization':'Bearer '+tok,
    'Accept':'application/vnd.github+json',
    'X-GitHub-Api-Version':'2022-11-28'})
with urllib.request.urlopen(req) as r:
    data=json.load(r)
runs=[]
for x in data.get('workflow_runs',[]):
    runs.append({k:x.get(k) for k in ('id','name','event','status','conclusion','head_sha','created_at','updated_at','run_attempt')})
print(json.dumps({'workflow':workflow,'runs':runs},sort_keys=True))
