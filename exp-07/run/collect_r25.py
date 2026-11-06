#!/usr/bin/env python3
import argparse,glob,json,sys
from pathlib import Path

ap=argparse.ArgumentParser()
ap.add_argument('--root',default='bundles')
ap.add_argument('--output',default='out/aggregate.json')
ap.add_argument('--expected',type=int,default=20)
a=ap.parse_args()

packages=[]
errors=[]
for p in glob.glob(f'{a.root}/**/package.json',recursive=True):
    try:
        q=json.load(open(p));q['_path']=p;packages.append(q)
    except Exception as e:
        errors.append({'path':p,'error':str(e)})

valid=[q for q in packages if q.get('engine')=='r25' and q.get('schema')==3]
ids=sorted(q.get('id') for q in valid if isinstance(q.get('id'),int))
missing=[i for i in range(a.expected) if i not in ids]

params={}
for key in ('parts','lo','hi','chunk','chunks','source'):
    params[key]=sorted({str(q.get(key)) for q in valid})

coverage_errors=[]
if len(valid)!=a.expected:
    coverage_errors.append(f'package_count={len(valid)} expected={a.expected}')
if ids!=list(range(a.expected)):
    coverage_errors.append(f'ids={ids}')
for key,vals in params.items():
    if len(vals)!=1:
        coverage_errors.append(f'{key}_values={vals}')

for q in valid:
    i=q['id']
    if q.get('parts')!=a.expected:
        coverage_errors.append(f'id={i} bad_parts={q.get("parts")}')
    if q.get('scientific_exit')!=0:
        coverage_errors.append(f'id={i} exit={q.get("scientific_exit")}')
    if not q.get('complete_no_hit'):
        coverage_errors.append(f'id={i} incomplete')
    if q.get('partial'):
        coverage_errors.append(f'id={i} partial')
    if q.get('hits')!=0:
        coverage_errors.append(f'id={i} hits={q.get("hits")}')
    if q.get('done')!=q.get('expected_chunks') or q.get('assigned')!=q.get('expected_chunks'):
        coverage_errors.append(
            f'id={i} expected={q.get("expected_chunks")} assigned={q.get("assigned")} done={q.get("done")}'
        )

# Independent partition arithmetic: every global chunk index must be owned by
# exactly one id modulo `parts`, and per-worker expected counts must sum to all chunks.
if valid and not any(len(params[k])!=1 for k in ('parts','lo','hi','chunk','chunks')):
    parts=int(params['parts'][0]);chunks=int(params['chunks'][0])
    if parts!=a.expected:
        coverage_errors.append(f'global parts={parts}')
    expected_sum=0
    for i in range(parts):
        n=0 if i>=chunks else (chunks-1-i)//parts+1
        expected_sum+=n
        matches=[q for q in valid if q.get('id')==i]
        if len(matches)==1 and matches[0].get('expected_chunks')!=n:
            coverage_errors.append(f'id={i} arithmetic_expected={n} package_expected={matches[0].get("expected_chunks")}')
    if expected_sum!=chunks:
        coverage_errors.append(f'partition_sum={expected_sum} chunks={chunks}')

out={
    'schema':3,
    'engine':'r25',
    'packages_seen':len(packages),
    'valid_packages':len(valid),
    'validated_ids':ids,
    'missing_ids':missing,
    'parameter_sets':params,
    'records':sum(int(q.get('records',0)) for q in valid),
    'groups':sum(int(q.get('groups',0)) for q in valid),
    'triples':sum(int(q.get('triples',0)) for q in valid),
    'orient':sum(int(q.get('orient',0)) for q in valid),
    'all3':sum(int(q.get('all3',0)) for q in valid),
    'exact':sum(int(q.get('exact',0)) for q in valid),
    'hits':sum(int(q.get('hits',0)) for q in valid),
    'parse_errors':errors,
    'coverage_errors':coverage_errors,
    'complete_no_hit':not errors and not coverage_errors,
}
Path(a.output).parent.mkdir(parents=True,exist_ok=True)
Path(a.output).write_text(json.dumps(out,sort_keys=True,indent=2)+'\n')
print(json.dumps(out,sort_keys=True))
if errors or coverage_errors:
    sys.exit(1)
