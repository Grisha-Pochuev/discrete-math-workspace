#!/usr/bin/env bash
# Caller bootstraps immutable p01 source archive first. Fail closed: no unguarded fallback.
set -euo pipefail
if [ "$#" -lt 3 ]; then echo 'source-root guard-output [prepare arguments...]' >&2; exit 64; fi
source_root="$1"; guard_output="$2"; shift 2
here="$(cd -- "$(dirname -- "$0")" && pwd)"
timeout --signal=TERM --kill-after=30s 1200s sudo -n --preserve-env "$(command -v python)" "$source_root/engine/vendor/memory_guard.py" \
  --output "$guard_output" -- "$(command -v python)" "$here/prepare.py" --source-root "$source_root" "$@"
