#!/usr/bin/env bash
# Invoke after preparing pinned inputs and compiling the checked binary.
set -euo pipefail
: "${SRC:?}" "${BUILD:?}" "${ASSIGNMENTS:?}" "${OUT:?}" "${JOB_DEADLINE:?}" "${JOB_INDEX:?}"
here=$(cd -- "$(dirname -- "$0")" && pwd)
python=$(command -v python)
mkdir -p -- "$OUT"
vendor=$SRC/engine/vendor
sudo -n --preserve-env "$python" "$vendor/smoke_memory_guard_checked.py" > "$OUT/smoke.json"
sudo -n --preserve-env "$python" "$vendor/memory_guard.py" --output "$OUT/guard" -- \
  "$python" "$here/m.py" --source "$SRC" --build "$BUILD" --assignments "$ASSIGNMENTS" \
  --output "$OUT/run" --index "$JOB_INDEX" --seconds 120 --deadline "$JOB_DEADLINE"
"$python" - "$OUT" <<'PY'
import json
from pathlib import Path
import sys
root = Path(sys.argv[1])
guard = json.loads((root/'guard'/'memory_result.json').read_text())
run = json.loads((root/'run'/'m.json').read_text())
if not (guard['status'] == 'completed' and guard['hard_limit_enforced']
        and guard['child_returncode'] == 0 and not guard['last']['populated']
        and not any(guard['last']['events'].get(k, 0)
                    for k in ('oom', 'oom_kill', 'oom_group_kill'))
        and guard['peak_bytes'] < guard['limits']['warn_bytes']
        and run['status'] == 'complete' and run['peak_searches'] == 4
        and run['all_searches_overlap_seconds'] >= 30
        and run['cpu_capacity']['usable_cores'] >= 4):
    raise SystemExit('four-worker runner smoke failed; retain all original output')
print(json.dumps({'memory_peak_bytes': guard['peak_bytes'], 'limits': guard['limits'],
                  'cpu_seconds': run['cpu_seconds'], 'wall_seconds': run['wall_seconds'],
                  'overlap_seconds': run['all_searches_overlap_seconds']}))
PY
