#!/usr/bin/env bash
set -euo pipefail

ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
cd "$ROOT"

echo "nproc=$(nproc)"
g++ -O3 -std=c++20 exp-07/src/w0.cpp -o /tmp/e07-w
python3 -m py_compile exp-07/src/v0.py exp-07/src/c0.py exp-07/run/collect.py

rm -rf out
mkdir -p out
/tmp/e07-w 0 0 1 100 30 out/n.tsv out/s.json 1e-14 >out/w.log 2>&1
python3 exp-07/src/v0.py --type 0 --input out/n.tsv --output out/v.json >out/v.log 2>&1

python3 - <<'PY'
import json
s=json.load(open('out/s.json'))
assert s['parameter_count']==1221,s
assert s['processed_assigned_u']==1221,s
assert s['type']==0 and s['limit']==100 and s['shards']==1 and s['shard']==0,s
v=json.load(open('out/v.json'))
assert v['exact_cancellations']==0,v
assert not v['solutions'],v
print('smoke_ok')
PY
