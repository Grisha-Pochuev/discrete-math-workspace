#!/usr/bin/env python3
import glob
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_SHARDS = 20
EXPECTED_COUNT = 49_679_870

files = sorted(glob.glob("artifacts/**/result-*.json", recursive=True))
parts = []
for name in files:
    with open(name, encoding="utf-8") as f:
        parts.append(json.load(f))

meta_files = glob.glob("artifacts/**/source.json", recursive=True)
source = {}
if meta_files:
    with open(meta_files[0], encoding="utf-8") as f:
        source = json.load(f)

sum_fields = [
    "processed",
    "rejected_r5_formula",
    "rejected_polynomial",
    "passed_local_factor_checks",
    "errors_count",
    "candidates_count",
]
totals = {key: sum(int(p.get(key, 0)) for p in parts) for key in sum_fields}
shards = sorted(int(p["shard"]) for p in parts)
line_counts = sorted(set(int(p.get("lines_seen", 0)) for p in parts))
r_hist = Counter()
candidates = []
errors = []
for p in parts:
    r_hist.update({str(k): int(v) for k, v in p.get("r_histogram", {}).items()})
    candidates.extend(p.get("candidates", []))
    errors.extend(p.get("errors", []))

complete = (
    len(parts) == EXPECTED_SHARDS
    and shards == list(range(EXPECTED_SHARDS))
    and totals["processed"] == EXPECTED_COUNT
    and totals["errors_count"] == 0
    and line_counts == [EXPECTED_COUNT]
)

result = {
    "status": "complete" if complete else "incomplete",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "dataset": source,
    "expected_numbers": EXPECTED_COUNT,
    "result_files": len(parts),
    "shards_present": shards,
    "line_counts_seen_by_workers": line_counts,
    "totals": totals,
    "max_r": max((int(p.get("max_r", 0)) for p in parts), default=0),
    "r_histogram": dict(sorted(r_hist.items(), key=lambda kv: int(kv[0]))),
    "candidates": candidates,
    "errors": errors,
    "workflow": {
        "repository": os.getenv("GITHUB_REPOSITORY", ""),
        "run_id": os.getenv("GITHUB_RUN_ID", ""),
        "sha": os.getenv("GITHUB_SHA", ""),
    },
}

out = Path("chebyshev-search/results")
out.mkdir(parents=True, exist_ok=True)
(out / "latest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

if complete and candidates:
    headline = f"FOUND {len(candidates)} COUNTEREXAMPLE CANDIDATE(S)"
elif complete:
    headline = "No counterexample among all Carmichael numbers below 10^22"
else:
    headline = "Scan incomplete — do not draw a mathematical conclusion"

summary = f"""# Chebyshev criterion: exhaustive Carmichael scan

**{headline}**

- Status: `{result['status']}`
- Dataset entries processed: `{totals['processed']:,}` / `{EXPECTED_COUNT:,}`
- Workers reported source line count: `{line_counts}`
- Result shards: `{len(parts)}` / `{EXPECTED_SHARDS}`
- Exact counterexample candidates: `{len(candidates)}`
- Unresolved computational errors: `{totals['errors_count']}`
- Largest prescribed `r` encountered: `{result['max_r']}`
- Source SHA-256: `{source.get('sha256', 'unknown')}`
- GitHub Actions run: `{result['workflow']['run_id']}`

The scanner factors each Carmichael number, checks the congruence modulo every
prime divisor using the Frobenius reduction, and independently rechecks any
survivor directly in `(Z/nZ)[x]/(x^r-1)`.  A complete negative result only
excludes the published Carmichael table below `10^22`; it does not prove the
criterion for all composite integers.
"""
(out / "SUMMARY.md").write_text(summary, encoding="utf-8")
print(summary)
if not complete:
    raise SystemExit(2)
