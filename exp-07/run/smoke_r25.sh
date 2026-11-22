#!/usr/bin/env bash
set -euo pipefail

ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
cd "$ROOT"

echo "nproc=$(nproc)"
g++ -O3 -march=native -std=c++20 exp-07/src/r25.cpp -o /tmp/e07-r25
python3 -m py_compile exp-07/run/collect_r25.py

rm -rf out
mkdir -p out
LO=12000000000000000001
HI=12000100000000000000
CHUNK=100000000000000
/tmp/e07-r25 "$LO" "$HI" "$CHUNK" 0 1 300 out/result.txt out/progress.txt >out/stdout.txt 2>out/stderr.txt

python3 - <<'PY'
import re
s=open('out/result.txt').read()
matches=re.findall(r'^STAT (.*)$',s,re.M)
assert matches,'missing STAT'
d={}
for item in matches[-1].split():
    if '=' in item:
        k,v=item.split('=',1);d[k]=v
expected={
    'lo':'12000000000000000001',
    'hi':'12000100000000000000',
    'chunk':'100000000000000',
    'part':'0','parts':'1','chunks':'1','assigned':'1','done':'1',
    'rec':'25708123','groups':'7','triples':'7','orient':'1',
    'k01_3':'0','all3':'0','exact':'0','hits':'0','max_group':'3',
    'max_trans':'2','partial':'0',
}
for k,v in expected.items():
    assert d.get(k)==v,(k,d.get(k),v,d)
print('r25_smoke_ok')
PY
