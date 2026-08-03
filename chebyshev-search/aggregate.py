#!/usr/bin/env python3
import glob
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_SHARDS = 20
EXPECTED_COUNT = 49_679_870
EXPECTED_FIRST = 561

parts = []
for name in sorted(glob.glob('artifacts/**/result-*.json', recursive=True)):
    with open(name, encoding='utf-8') as f:
        parts.append(json.load(f))
parts.sort(key=lambda p: int(p['shard']))

source = {}
meta_files = glob.glob('artifacts/**/source.json', recursive=True)
if meta_files:
    with open(meta_files[0], encoding='utf-8') as f:
        source = json.load(f)

sum_fields = [
    'lines_seen', 'processed', 'malformed', 'rejected_r5_formula',
    'rejected_polynomial', 'passed_local_factor_checks',
    'errors_count', 'candidates_count',
]
totals = {key: sum(int(p.get(key, 0)) for p in parts) for key in sum_fields}
shards = [int(p['shard']) for p in parts]
r_hist = Counter()
candidates = []
errors = []
for p in parts:
    r_hist.update({str(k): int(v) for k, v in p.get('r_histogram', {}).items()})
    candidates.extend(p.get('candidates', []))
    errors.extend(p.get('errors', []))

strict_boundaries = True
for left, right in zip(parts, parts[1:]):
    if int(left.get('last_n', 0)) >= int(right.get('first_n', 0)):
        strict_boundaries = False
        break

complete = (
    len(parts) == EXPECTED_SHARDS
    and shards == list(range(EXPECTED_SHARDS))
    and totals['processed'] == EXPECTED_COUNT
    and totals['lines_seen'] == EXPECTED_COUNT
    and totals['malformed'] == 0
    and totals['errors_count'] == 0
    and bool(parts)
    and int(parts[0].get('first_n', 0)) == EXPECTED_FIRST
    and strict_boundaries
)

result = {
    'status': 'complete' if complete else 'incomplete',
    'generated_at': datetime.now(timezone.utc).isoformat(),
    'dataset': source,
    'expected_numbers': EXPECTED_COUNT,
    'result_files': len(parts),
    'shards_present': shards,
    'strictly_increasing_shard_boundaries': strict_boundaries,
    'first_n': parts[0].get('first_n') if parts else None,
    'last_n': parts[-1].get('last_n') if parts else None,
    'totals': totals,
    'max_r': max((int(p.get('max_r', 0)) for p in parts), default=0),
    'r_histogram': dict(sorted(r_hist.items(), key=lambda kv: int(kv[0]))),
    'candidates': candidates,
    'errors': errors,
    'workflow': {
        'repository': os.getenv('GITHUB_REPOSITORY', ''),
        'run_id': os.getenv('GITHUB_RUN_ID', ''),
        'sha': os.getenv('GITHUB_SHA', ''),
    },
}

out = Path('chebyshev-search/results')
out.mkdir(parents=True, exist_ok=True)
(out / 'latest.json').write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

if complete and candidates:
    headline = f'FOUND {len(candidates)} COUNTEREXAMPLE CANDIDATE(S)'
elif complete:
    headline = 'No counterexample in the complete published Carmichael table below 10^22'
else:
    headline = 'Scan incomplete — no mathematical conclusion is valid'

summary = f'''# Chebyshev criterion: exhaustive Carmichael scan

**{headline}**

- Status: `{result["status"]}`
- Dataset rows processed: `{totals["processed"]:,}` / `{EXPECTED_COUNT:,}`
- Result shards: `{len(parts)}` / `{EXPECTED_SHARDS}`
- Strict shard boundaries: `{strict_boundaries}`
- First/last number: `{result["first_n"]}` / `{result["last_n"]}`
- Exact counterexample candidates: `{len(candidates)}`
- Malformed source rows: `{totals["malformed"]}`
- Unresolved computational errors: `{totals["errors_count"]}`
- Largest prescribed `r` encountered: `{result["max_r"]}`
- Source URL: `{source.get("url", "unknown")}`
- Source ETag: `{source.get("etag", "unknown")}`
- Source bytes: `{source.get("bytes", "unknown")}`
- GitHub Actions run: `{result["workflow"]["run_id"]}`

For each published Carmichael number the scanner reads its complete prime
factorization, computes the prescribed smallest `r`, checks the Frobenius-
reduced congruence modulo every prime divisor, and independently recomputes the
original congruence modulo `n` for every survivor. A complete negative result
excludes this finite table only; it is not a proof for all composite integers.
'''
(out / 'SUMMARY.md').write_text(summary, encoding='utf-8')
print(summary)
if not complete:
    raise SystemExit(2)
