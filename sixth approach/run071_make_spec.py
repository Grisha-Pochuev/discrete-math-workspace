#!/usr/bin/env python3
"""Create the immutable run-071 search specification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
EVENT_RELATIVE = "sixth approach/specs/run-071-exact-event-cuts.json"
EVENT_PATH = HERE / "specs" / "run-071-exact-event-cuts.json"
OUTPUT = HERE / "specs" / "run-071-boundary-event.json"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    event = json.loads(EVENT_PATH.read_text(encoding="utf-8"))
    if event["schema"] != "boundary-exact-event-cuts-v1" or event["cut_count"] != 2:
        raise ValueError("wrong event-cut bundle")
    searches = []
    first_seed = 20894331
    for offset in range(72):
        searches.append({
            "id": f"s{80 + offset:03d}",
            "group": offset // 4,
            "slot": offset % 4,
            "seed": first_seed + 7919 * offset,
            "target_orbit": (offset + 2) % 3,
        })
    spec = {
        "schema": "run-071-boundary-event-v1",
        "run_id": "run-071",
        "scope": "bounded constructive support search with two independently accepted exact-event clauses",
        "engine": "ortools-cp-sat-9.15.6755-lazy-support",
        "active_variables": 324,
        "boundary_rows": 29160,
        "physical_jobs": 18,
        "reserved_runner_slots": 2,
        "logical_workers_per_job": 4,
        "seconds_per_search": 18000,
        "seconds_per_round": 120,
        "max_rounds": 500,
        "cuts_per_round": 512,
        "memory_mib_per_search": 3000,
        "event_cut_path": EVENT_RELATIVE,
        "event_cut_sha256": sha256(EVENT_PATH),
        "event_cut_outcome_sha256": event["canonical_outcome_sha256"],
        "searches": searches,
        "source_hashes": {
            "run070_contract.py": sha256(HERE / "run070_contract.py"),
            "run071_worker.py": sha256(HERE / "run071_worker.py"),
            "run071_collect.py": sha256(HERE / "run071_collect.py"),
        },
    }
    OUTPUT.write_text(
        json.dumps(spec, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({
        "output": str(OUTPUT),
        "searches": len(searches),
        "groups": len({item["group"] for item in searches}),
        "event_cut_sha256": spec["event_cut_sha256"],
        "spec_sha256": sha256(OUTPUT),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
