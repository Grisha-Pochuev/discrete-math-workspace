#!/usr/bin/env python3
import json,sys

def check(b):
    if len(b)!=9 or any(x<=0 for x in b) or len(set(b))!=9:
        return False
    c=[x**3 for x in b]
    s=[sum(c[0:3]),sum(c[3:6]),sum(c[6:9]),c[0]+c[3]+c[6],c[1]+c[4]+c[7],c[2]+c[5]+c[8]]
    return len(set(s))==1

ok=True
for path in sys.argv[1:]:
    data=json.load(open(path))
    for item in data.get('found',[]):
        if not check([int(x) for x in item['bases']]):
            ok=False
            print('bad',path,item,file=sys.stderr)
if not ok:
    raise SystemExit(1)
print('ok')
