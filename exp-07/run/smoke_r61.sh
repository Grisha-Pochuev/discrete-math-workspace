#!/usr/bin/env bash
set -euo pipefail
g++ -O3 -march=native -std=c++20 exp-07/src/r61.cpp -o /tmp/e07-r61-smoke
out="$(/tmp/e07-r61-smoke 100000000000 0 1 20000 128 60)"
printf '%s\n' "$out"
grep -q 'wheel=16943706 wheel_res=4' <<<"$out"
grep -q 'survivors=0 partial=0' <<<"$out"
