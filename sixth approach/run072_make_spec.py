#!/usr/bin/env python3
"""Build the immutable neutral specification for run-072."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = HERE / "specs" / "run-072-finite-events.json"
INPUT = HERE / "specs" / "run-072-event-input.json.gz"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    searches = []
    for index in range(80):
        searches.append({
            "id": f"s{index:03d}",
            "group": index // 4,
            "slot": index % 4,
            "seed": 30790001 + index * 7919,
        })
    payload = {
        "schema": "run-072-finite-events-v1",
        "run_id": "run-072",
        "scope": "bounded independent continuation from a replayed finite-event frontier",
        "engine": "ortools-cp-sat-9.15.6755-single-thread-cegis",
        "input_path": "sixth approach/specs/run-072-event-input.json.gz",
        "input_sha256": sha(INPUT),
        "input_outcome_sha256": "86e18dd15453029af75a5856fd2dae47dd0176832b6ca2458173a64566d786da",
        "base_source_clauses": 325,
        "base_learned_clauses": 1562,
        "base_total_clauses": 1887,
        "physical_jobs": 20,
        "reserved_runner_slots": 0,
        "logical_workers_per_job": 4,
        "seconds_per_search": 18000,
        "seconds_per_round": 120,
        "max_rounds": 500,
        "cuts_per_round": 512,
        "memory_mib_per_search": 3000,
        "searches": searches,
        "source_hashes": {
            name: sha(HERE / name)
            for name in ("run072_contract.py", "run072_worker.py", "run072_collect.py")
        },
    }
    SPEC.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )


if __name__ == "__main__":
    main()
