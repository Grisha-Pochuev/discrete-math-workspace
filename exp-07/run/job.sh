#!/usr/bin/env bash
set -euo pipefail

id="${1:?matrix id required}"
limit="${2:-2350}"
seconds="${3:-19800}"

if (( id < 0 || id > 19 )); then echo "bad id=$id" >&2; exit 2; fi
if (( limit < 2 )); then echo "bad limit=$limit" >&2; exit 2; fi
if (( seconds < 1 || seconds > 19800 )); then echo "seconds must be 1..19800" >&2; exit 2; fi

if   (( id < 4 ));  then t=0; g=$id;        gs=4
elif (( id < 8 ));  then t=1; g=$((id-4));  gs=4
elif (( id < 11 )); then t=2; g=$((id-8));  gs=3
elif (( id < 14 )); then t=3; g=$((id-11)); gs=3
elif (( id < 17 )); then t=4; g=$((id-14)); gs=3
else                     t=5; g=$((id-17)); gs=3
fi

ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
cd "$ROOT"
rm -rf out
mkdir -p out/raw

g++ -O3 -std=c++20 exp-07/src/w0.cpp -o /tmp/e07-w
python3 -m py_compile exp-07/src/v0.py exp-07/src/c0.py

{
  date -u +%FT%TZ
  uname -a
  nproc
  lscpu
  free -h
  g++ --version
  python3 --version
  echo "source=${GITHUB_SHA:-local}"
  echo "id=$id type=$t group=$g groups=$gs limit=$limit seconds=$seconds"
} > out/raw/machine.txt

set +e
timeout --signal=TERM --kill-after=60s "$((seconds+120))s" \
  /tmp/e07-w "$t" "$g" "$gs" "$limit" "$seconds" \
    out/raw/n.tsv out/raw/s.json 1e-14 \
    >out/raw/w.log 2>&1
code=$?
set -e
echo "$code" > out/raw/e.txt
test "$code" -eq 0

python3 - "$t" "$g" "$gs" "$limit" <<'PY'
import json,sys
t,g,gs,limit=map(int,sys.argv[1:])
s=json.load(open('out/raw/s.json'))
assert s['type']==t and s['shard']==g and s['shards']==gs and s['limit']==limit,s
PY

python3 exp-07/src/v0.py --type "$t" --input out/raw/n.tsv --output out/raw/v.json >out/raw/v.log 2>&1

tar -C out/raw -czf out/d.tgz .
key="$(openssl rand -hex 32)"
openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 \
  -in out/d.tgz -out out/d.enc -pass pass:"$key"
printf '%s' "$key" > out/k.txt
openssl pkeyutl -encrypt -pubin -inkey exp-07/k0.pub \
  -in out/k.txt -out out/k.enc \
  -pkeyopt rsa_padding_mode:oaep -pkeyopt rsa_oaep_md:sha256
sha256sum out/d.enc out/k.enc > out/checksums.sha256

python3 - "$id" "$t" "$g" "$gs" "$limit" "$seconds" <<'PY'
import hashlib,json,os,sys
id,t,g,gs,limit,seconds=map(int,sys.argv[1:])
def h(p):
    x=hashlib.sha256(); x.update(open(p,'rb').read()); return x.hexdigest()
data={
  'schema':2,
  'id':id,
  'class':t,
  'group':g,
  'groups':gs,
  'shards':gs,
  'limit':limit,
  'seconds':seconds,
  'source':os.environ.get('GITHUB_SHA','local'),
  'run_id':os.environ.get('GITHUB_RUN_ID'),
  'validated':True,
  'detail_sha256':h('out/d.enc'),
  'key_sha256':h('out/k.enc')
}
open('out/package.json','w').write(json.dumps(data,sort_keys=True,indent=2)+'\n')
PY

rm -rf out/raw out/d.tgz out/k.txt
