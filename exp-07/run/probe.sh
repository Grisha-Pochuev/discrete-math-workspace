#!/usr/bin/env bash
# canonical probe runner; repeated-difference lists are fetched and independently replayed
set -euo pipefail

target="${1:-}"
case "$target" in r7|r8|r9|r10|r11|r13|r14|r15|r16|r17|r18) ;; *) echo "bad target" >&2; exit 2;; esac
mkdir -p out/plain

if [ "$target" = r7 ]; then
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
    r15|r16|r17)
      set -e
      curl -fsSL --retry 3 https://oeis.org/A265625/b265625.txt -o out/plain/b3plus.txt
      sha256sum out/plain/b3plus.txt > out/plain/sources.sha256
      set +e
      "/tmp/${target}" out/plain/b3plus.txt out/plain/result.txt >out/plain/stdout.txt 2>out/plain/stderr.txt
      RC=$?
      ;;
    r18)
      set -e
      curl -fsSL --retry 3 https://oeis.org/A265625/b265625.txt -o out/plain/bplus.txt
      curl -fsSL --retry 3 https://oeis.org/A014441/b014441.txt -o out/plain/b3.txt
      curl -fsSL --retry 3 https://oeis.org/A333376/b333376.txt -o out/plain/b4.txt
      curl -fsSL --retry 3 https://oeis.org/A333377/b333377.txt -o out/plain/b5.txt
      sha256sum out/plain/bplus.txt out/plain/b3.txt out/plain/b4.txt out/plain/b5.txt > out/plain/sources.sha256
      set +e
      /tmp/r18 out/plain/bplus.txt out/plain/b3.txt out/plain/b4.txt out/plain/b5.txt out/plain/result.txt >out/plain/stdout.txt 2>out/plain/stderr.txt
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
