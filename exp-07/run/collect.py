#!/usr/bin/env python3
import argparse, glob, json, sys
from pathlib import Path

ap=argparse.ArgumentParser()
ap.add_argument('--root',default='bundles')
ap.add_argument('--output',default='out/aggregate.json')
ap.add_argument('--expected',type=int,default=20)
a=ap.parse_args()

packages=[]
for p in glob.glob(f'{a.root}/**/package.json',recursive=True):
    try:
        packages.append(json.load(open(p)))
    except Exception as e:
        packages.append({'path':p,'parse_error':str(e)})

ids=sorted(x['id'] for x in packages if x.get('validated') is True and 'id' in x)
sources=sorted(set(x.get('source') for x in packages if x.get('source')))
missing=[i for i in range(a.expected) if i not in ids]
out={
    'schema':2,
    'packages':len(packages),
    'validated_ids':ids,
    'missing_ids':missing,
    'sources':sources,
}
Path(a.output).parent.mkdir(parents=True,exist_ok=True)
Path(a.output).write_text(json.dumps(out,sort_keys=True,indent=2)+'\n')
print(json.dumps(out,sort_keys=True))
if missing or ids != list(range(a.expected)) or len(sources)!=1:
    sys.exit(1)
