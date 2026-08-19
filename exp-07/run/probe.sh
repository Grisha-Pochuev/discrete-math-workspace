#!/usr/bin/env bash
# canonical probe runner; repeated-difference lists are fetched and independently replayed
set -euo pipefail

target="${1:-}"
case "$target" in lit|meta|r7|r8|r9|r10|r11|r13|r14|r15|r16|r17|r18|r19|r21|r22|r23|r24) ;; *) echo "bad target" >&2; exit 2;; esac
mkdir -p out/plain

if [ "$target" = lit ]; then
  set -euo pipefail
  urls=(
    'https://www.sciencedirect.com/science/article/pii/S0022314X04001866/pdfft?isDTMRedir=true&download=true'
    'https://api.elsevier.com/content/article/pii/S0022314X04001866?httpAccept=application/pdf'
  )
  ok=0
  for u in "${urls[@]}"; do
    if curl -fL --retry 2 --connect-timeout 20 --max-time 90 \
      -A 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36' \
      -H 'Accept: application/pdf,*/*;q=0.8' "$u" -o out/plain/paper.bin 2>>out/plain/curl.err; then
      if head -c 5 out/plain/paper.bin | grep -q '%PDF-'; then ok=1; printf '%s\n' "$u" > out/plain/source.txt; break; fi
    fi
  done
  if [ "$ok" -ne 1 ]; then
    echo 'PDF_FETCH_FAIL' | tee out/summary.txt
    wc -c out/plain/paper.bin 2>/dev/null || true
    exit 21
  fi
  if ! command -v pdftotext >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq poppler-utils
  fi
  pdftotext -layout out/plain/paper.bin out/plain/paper.txt
  python3 - <<'PY' | tee out/summary.txt
import re, hashlib
from pathlib import Path
p=Path('out/plain/paper.bin').read_bytes()
t=Path('out/plain/paper.txt').read_text(errors='replace')
print('PDF_OK bytes=%d text_chars=%d sha256=%s' % (len(p),len(t),hashlib.sha256(p).hexdigest()))
lines=t.splitlines()
keys=('pairwise sums','six integers','eight integers','diophantine chain','we obtain','are cubes','is a cube')
idx=[]
for i,line in enumerate(lines):
    low=line.lower()
    if any(k in low for k in keys): idx.append(i)
keep=[]
for i in idx:
    for j in range(max(0,i-3),min(len(lines),i+8)):
        if j not in keep: keep.append(j)
for j in keep[:140]:
    s=lines[j].rstrip()
    if s: print(f'L{j+1}: {s[:300]}')
PY
  rm -f out/plain/paper.bin out/plain/paper.txt
elif [ "$target" = meta ]; then
  python3 exp-07/run/runmeta.py e07-d2.yml | tee out/plain/meta.json | tee out/summary.txt
elif [ "$target" = r7 ]; then
  python3 -m pip install --disable-pip-version-check -q sympy==1.14.0
  python3 exp-07/src/r7.py --min-m 3 --max-m 5 --output out/plain/result.json >out/plain/stdout.txt 2>out/plain/stderr.txt
  python3 - <<'PY' | tee out/summary.txt
import json
d=json.load(open('out/plain/result.json'))
print('families='+str(d['families']))
print('roots_gt1='+str(d['rational_roots_gt1_with_multiplicity']))
print('exact_candidates='+str(d['positive_distinct_exact_candidates']))
print('hits='+str(d['unique_hits']))
print('elapsed_seconds='+str(d['elapsed_seconds']))
PY
elif [ "$target" = r21 ]; then
  python3 -m pip install --disable-pip-version-check -q sympy==1.14.0
  python3 exp-07/src/r21.py >out/plain/stdout.txt 2>out/plain/stderr.txt
  cat out/plain/stdout.txt | tee out/summary.txt
else
  if ! dpkg -s libgmp-dev >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq libgmp-dev
  fi
  g++ -O3 -march=native -std=c++20 "exp-07/src/${target}.cpp" -lgmpxx -lgmp -o "/tmp/${target}"
  set +e
  case "$target" in
    r8|r9|r10|r13)
      read H FILTERS < "exp-07/run/${target}.cfg"
      [[ "$H" =~ ^[0-9]+$ && "$FILTERS" =~ ^[0-9]+$ ]]
      "/tmp/${target}" "$H" 0 1 out/plain/result.txt "$FILTERS" >out/plain/stdout.txt 2>out/plain/stderr.txt
      RC=$?
      ;;
    r11)
      /tmp/r11 100 out/plain/result.txt >out/plain/stdout.txt 2>out/plain/stderr.txt
      RC=$?
      ;;
    r14)
      set -e
      curl -fsSL --retry 3 https://oeis.org/A333376/b333376.txt -o out/plain/b4.txt
      curl -fsSL --retry 3 https://oeis.org/A333377/b333377.txt -o out/plain/b5.txt
      sha256sum out/plain/b4.txt out/plain/b5.txt > out/plain/sources.sha256
      set +e
      /tmp/r14 out/plain/b4.txt out/plain/b5.txt out/plain/result.txt >out/plain/stdout.txt 2>out/plain/stderr.txt
      RC=$?
      ;;
    r15|r16|r17|r22|r23)
      set -e
      curl -fsSL --retry 3 https://oeis.org/A265625/b265625.txt -o out/plain/b3plus.txt
      sha256sum out/plain/b3plus.txt > out/plain/sources.sha256
      set +e
      "/tmp/${target}" out/plain/b3plus.txt out/plain/result.txt >out/plain/stdout.txt 2>out/plain/stderr.txt
      RC=$?
      ;;
    r18|r19)
      set -e
      curl -fsSL --retry 3 https://oeis.org/A265625/b265625.txt -o out/plain/bplus.txt
      curl -fsSL --retry 3 https://oeis.org/A014441/b014441.txt -o out/plain/b3.txt
      curl -fsSL --retry 3 https://oeis.org/A333376/b333376.txt -o out/plain/b4.txt
      curl -fsSL --retry 3 https://oeis.org/A333377/b333377.txt -o out/plain/b5.txt
      sha256sum out/plain/bplus.txt out/plain/b3.txt out/plain/b4.txt out/plain/b5.txt > out/plain/sources.sha256
      set +e
      "/tmp/${target}" out/plain/bplus.txt out/plain/b3.txt out/plain/b4.txt out/plain/b5.txt out/plain/result.txt >out/plain/stdout.txt 2>out/plain/stderr.txt
      RC=$?
      ;;
    r24)
      /tmp/r24 12000000000000000001 12000100000000000000 out/plain/result.txt >out/plain/stdout.txt 2>out/plain/stderr.txt
      RC=$?
      ;;
  esac
  set -e
  if [ "$RC" -ne 0 ] && [ "$RC" -ne 10 ]; then exit "$RC"; fi
  grep '^STAT ' out/plain/result.txt | tail -1 | tee out/summary.txt
  printf 'rc=%s\n' "$RC" >> out/summary.txt
fi

tar -C out/plain -czf out/r.tgz .
key="$(openssl rand -hex 32)"
openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 -in out/r.tgz -out out/r.enc -pass pass:"$key"
printf '%s' "$key" > out/k.txt
openssl pkeyutl -encrypt -pubin -inkey exp-07/k0.pub -in out/k.txt -out out/k.enc -pkeyopt rsa_padding_mode:oaep -pkeyopt rsa_oaep_md:sha256
sha256sum out/r.enc out/k.enc > out/checksums.sha256
rm -rf out/plain out/r.tgz out/k.txt
