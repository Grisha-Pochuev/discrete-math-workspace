#!/usr/bin/env bash
set -euo pipefail
id="${1:?matrix id required}"
N="${2:?N required}"
pmax="${3:-20000}"
filters="${4:-128}"
seconds="${5:-19800}"
parts=20
if (( id < 0 || id >= parts )); then echo "bad id=$id" >&2; exit 2; fi
for x in "$N" "$pmax" "$filters" "$seconds"; do [[ "$x" =~ ^[0-9]+$ ]] || { echo bad numeric >&2; exit 2; }; done
if (( pmax < 100 || filters < 1 || seconds < 1 || seconds > 19800 )); then echo "bad limits" >&2; exit 2; fi
ROOT="${GITHUB_WORKSPACE:-$(pwd)}"; cd "$ROOT"; rm -rf out; mkdir -p out/raw
g++ -O3 -march=native -std=c++20 exp-07/src/r61.cpp -o /tmp/e07-r61
{
 date -u +%FT%TZ; uname -a; nproc; free -h; g++ --version | head -1
 echo "source=${GITHUB_SHA:-local}"
 echo "id=$id parts=$parts N=$N pmax=$pmax filters=$filters seconds=$seconds"
} > out/raw/machine.txt
set +e
timeout --signal=TERM --kill-after=60s "$((seconds+120))s" /tmp/e07-r61 "$N" "$id" "$parts" "$pmax" "$filters" "$seconds" >out/raw/result.txt 2>out/raw/stderr.txt
code=$?
set -e
printf '%s\n' "$code" >out/raw/exit_code.txt
python3 - "$id" "$parts" "$N" "$pmax" "$filters" "$code" <<'PY'
import json,re,sys
id,parts=int(sys.argv[1]),int(sys.argv[2]); N=int(sys.argv[3]); pmax=int(sys.argv[4]); filters=int(sys.argv[5]); code=int(sys.argv[6])
t=open('out/raw/result.txt',errors='replace').read(); ms=re.findall(r'^STAT (.*)$',t,re.M)
if not ms: raise SystemExit('missing STAT')
d={}
for q in ms[-1].split():
    if '=' in q:
        k,v=q.split('=',1); d[k]=v
for k,v in {'N':N,'part':id,'parts':parts,'pmax':pmax,'filters':filters,'wheel':16943706,'wheel_res':4}.items():
    if int(d.get(k,'-1'))!=v: raise SystemExit(f'STAT mismatch {k}: {d.get(k)} != {v}')
W=16943706; R=(0,1,822511,16943705)
expected=0
for r in R:
    if r>N: continue
    k0=max(0,(2-r+W-1)//W); kmax=(N-r)//W
    if k0>kmax: continue
    rem=k0%parts
    if rem!=id: k0 += (id+parts-rem)%parts
    if k0<=kmax: expected += 2*((kmax-k0)//parts+1)
done=int(d.get('done','-1')); assigned=int(d.get('assigned','-1')); surv=int(d.get('survivors','-1')); partial=int(d.get('partial','-1'))
if code==0:
    if partial or surv or assigned!=expected or done!=expected: raise SystemExit(f'incomplete success expected={expected} assigned={assigned} done={done} surv={surv} partial={partial}')
elif code==10:
    if surv<=0: raise SystemExit('survivor exit without survivor')
elif code==124:
    if partial!=1: raise SystemExit('partial exit without flag')
else: raise SystemExit(f'unexpected scientific exit {code}')
open('out/raw/parsed.json','w').write(json.dumps({'expected':expected,'stat':d,'scientific_exit':code},sort_keys=True,indent=2)+'\n')
PY

tar -C out/raw -czf out/d.tgz .
key="$(openssl rand -hex 32)"
openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 -in out/d.tgz -out out/d.enc -pass pass:"$key"
printf '%s' "$key" >out/k.txt
openssl pkeyutl -encrypt -pubin -inkey exp-07/k0.pub -in out/k.txt -out out/k.enc -pkeyopt rsa_padding_mode:oaep -pkeyopt rsa_oaep_md:sha256
sha256sum out/d.enc out/k.enc >out/checksums.sha256
python3 - "$id" "$parts" "$N" "$pmax" "$filters" "$seconds" "$code" <<'PY'
import hashlib,json,os,sys
id,parts=int(sys.argv[1]),int(sys.argv[2]); N=int(sys.argv[3]); pmax=int(sys.argv[4]); filters=int(sys.argv[5]); seconds=int(sys.argv[6]); code=int(sys.argv[7])
p=json.load(open('out/raw/parsed.json')); d=p['stat']
def h(path): return hashlib.sha256(open(path,'rb').read()).hexdigest()
out={'schema':4,'engine':'r61','id':id,'parts':parts,'N':N,'pmax':pmax,'filters':filters,'seconds':seconds,
'wheel':int(d['wheel']),'wheel_res':int(d['wheel_res']),'expected':p['expected'],'assigned':int(d['assigned']),'done':int(d['done']),
'survivors':int(d['survivors']),'partial':bool(int(d['partial'])),'scientific_exit':code,
'complete_no_survivor':code==0 and int(d['partial'])==0 and int(d['survivors'])==0 and int(d['done'])==p['expected'],
'source':os.environ.get('GITHUB_SHA','local'),'run_id':os.environ.get('GITHUB_RUN_ID'),'detail_sha256':h('out/d.enc'),'key_sha256':h('out/k.enc')}
open('out/package.json','w').write(json.dumps(out,sort_keys=True,indent=2)+'\n')
PY
rm -rf out/raw out/d.tgz out/k.txt
exit "$code"
