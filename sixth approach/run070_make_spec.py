#!/usr/bin/env python3
"""Generate the canonical immutable run-070 search specification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    searches = []
    for index in range(80):
        searches.append(
            {
                "id": f"s{index:03d}",
                "group": index // 4,
                "slot": index % 4,
                "target_orbit": index % 3,
                "seed": 20260811 + 7919 * index,
            }
        )
    spec = {
        "schema": "run-070-boundary-support-v1",
        "run_id": "run-070",
        "engine": "ortools-cp-sat-9.15.6755-lazy-support",
        "physical_jobs": 20,
        "logical_workers_per_job": 4,
        "seconds_per_search": 18000,
        "seconds_per_round": 120,
        "memory_mib_per_search": 3000,
        "max_rounds": 500,
        "cuts_per_round": 512,
        "active_variables": 324,
        "boundary_rows": 29160,
        "scope": "bounded constructive support search with exact target existence and zero-or-multiple necessary rows",
        "source_hashes": {
            name: sha256(ROOT / name)
            for name in ("run070_contract.py", "run070_worker.py", "run070_collect.py")
        },
        "searches": searches,
    }
    output = ROOT / "specs" / "run-070-boundary-support.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(sha256(output))


if __name__ == "__main__":
    main()
