#!/usr/bin/env bash
set -euo pipefail

id="${1:?matrix id required}"
lo="${2:?lo required}"
hi="${3:?hi required}"
chunk="${4:?chunk required}"
seconds="${5:-19800}"
parts=20

if (( id < 0 || id >= parts )); then echo "bad id=$id" >&2; exit 2; fi
if [[ ! "$lo" =~ ^[0-9]+$ || ! "$hi" =~ ^[0-9]+$ || ! "$chunk" =~ ^[0-9]+$ ]]; then
  echo "bad numeric range" >&2; exit 2
fi
if (( seconds < 1 || seconds > 19800 )); then echo "seconds must be 1..19800" >&2; exit 2; fi

ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
cd "$ROOT"
rm -rf out
mkdir -p out/raw

g++ -O3 -march=native -std=c++20 exp-07/src/r25.cpp -lgmpxx -lgmp -o /tmp/e07-r25

{
  date -u +%FT%TZ
  uname -a
  nproc
  free -h
  g++ --version | head -1
  echo "source=${GITHUB_SHA:-local}"
  echo "id=$id parts=$parts lo=$lo hi=$hi chunk=$chunk seconds=$seconds"
} > out/raw/machine.txt

set +e
timeout --signal=TERM --kill-after=60s "$((seconds+120))s" \
  /tmp/e07-r25 "$lo" "$hi" "$chunk" "$id" "$parts" "$seconds" \
    out/raw/result.txt out/raw/progress.txt \
    >out/raw/stdout.txt 2>out/raw/stderr.txt
code=$?
set -e
printf '%s\n' "$code" > out/raw/exit_code.txt

python3 - "$id" "$parts" "$lo" "$hi" "$chunk" "$seconds" "$code" <<'PY'
import json,re,sys
id,parts,lo,hi,chunk,seconds,code=map(int,sys.argv[1:])
text=open('out/raw/result.txt',errors='replace').read() if __import__('os').path.exists('out/raw/result.txt') else ''
matches=re.findall(r'^STAT (.*)$',text,re.M)
if not matches:
    raise SystemExit('missing STAT')
d={}
for item in matches[-1].split():
    if '=' in item:
        k,v=item.split('=',1); d[k]=v
want={'lo':lo,'hi':hi,'chunk':chunk,'part':id,'parts':parts}
for k,v in want.items():
    if int(d.get(k,'-1'))!=v:
        raise SystemExit(f'STAT mismatch {k}: {d.get(k)} != {v}')
chunks=(hi-lo)//chunk+1
expected=0 if id>=chunks else (chunks-1-id)//parts+1
done=int(d.get('done','-1'))
assigned=int(d.get('assigned','-1'))
partial=int(d.get('partial','-1'))
hits=int(d.get('hits','-1'))
if code==0:
    if partial!=0 or hits!=0 or done!=expected or assigned!=expected:
        raise SystemExit(f'incomplete success: expected={expected} done={done} assigned={assigned} partial={partial} hits={hits}')
elif code==10:
    if hits<=0:
        raise SystemExit('hit exit without hit')
elif code==124:
    if partial!=1:
        raise SystemExit('partial exit without partial flag')
else:
    raise SystemExit(f'unexpected scientific exit {code}')
open('out/raw/parsed.json','w').write(json.dumps({
    'expected_chunks':expected,'stat':d,'scientific_exit':code
},sort_keys=True,indent=2)+'\n')
PY
parse_code=$?

# Package details even for a scientific hit/partial so the result is inspectable.
tar -C out/raw -czf out/d.tgz .
key="$(openssl rand -hex 32)"
openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 \
  -in out/d.tgz -out out/d.enc -pass pass:"$key"
printf '%s' "$key" > out/k.txt
openssl pkeyutl -encrypt -pubin -inkey exp-07/k0.pub \
  -in out/k.txt -out out/k.enc \
  -pkeyopt rsa_padding_mode:oaep -pkeyopt rsa_oaep_md:sha256
sha256sum out/d.enc out/k.enc > out/checksums.sha256

python3 - "$id" "$parts" "$lo" "$hi" "$chunk" "$seconds" "$code" <<'PY'
import hashlib,json,os,sys
id,parts,lo,hi,chunk,seconds,code=map(int,sys.argv[1:])
p=json.load(open('out/raw/parsed.json'))
d=p['stat']
def h(path):
    x=hashlib.sha256();x.update(open(path,'rb').read());return x.hexdigest()
data={
  'schema':3,
  'engine':'r25',
  'id':id,'part':id,'parts':parts,
  'lo':lo,'hi':hi,'chunk':chunk,'seconds':seconds,
  'chunks':int(d['chunks']),
  'expected_chunks':p['expected_chunks'],
  'assigned':int(d['assigned']),'done':int(d['done']),
  'last_lo':int(d['last_lo']),'last_hi':int(d['last_hi']),
  'records':int(d['rec']),'groups':int(d['groups']),'triples':int(d['triples']),
  'orient':int(d['orient']),'all3':int(d['all3']),'exact':int(d['exact']),'hits':int(d['hits']),
  'partial':bool(int(d['partial'])),
  'scientific_exit':code,
  'complete_no_hit':code==0 and int(d['partial'])==0 and int(d['hits'])==0 and int(d['done'])==p['expected_chunks'],
  'source':os.environ.get('GITHUB_SHA','local'),
  'run_id':os.environ.get('GITHUB_RUN_ID'),
  'detail_sha256':h('out/d.enc'),'key_sha256':h('out/k.enc')
}
open('out/package.json','w').write(json.dumps(data,sort_keys=True,indent=2)+'\n')
PY

rm -rf out/raw out/d.tgz out/k.txt

# A full negative certificate requires every worker to return zero. Hits and
# partials deliberately make the matrix non-success while preserving artifacts.
exit "$code"
