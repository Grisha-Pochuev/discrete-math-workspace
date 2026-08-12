#!/usr/bin/env python3
"""Generate the immutable neutral run specification."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    files = {
        "types": "sixth approach/specs/run-073-types.json",
        "input": "sixth approach/specs/run-073-input.json",
        "input_acceptance": "sixth approach/specs/run-073-input-acceptance.json",
        "support_hint": "sixth approach/specs/run-073-support-hint.json",
        "worker": "sixth approach/run073_worker.py",
        "verifier": "sixth approach/run073_verify.py",
        "logic": "sixth approach/run073_logic.py",
        "contract": "sixth approach/run073_contract.py",
        "collector": "sixth approach/run073_collect.py",
    }
    hashes = {name: sha256(args.root / path) for name, path in files.items()}
    searches = []
    seed_start = 1009
    seed_step = 104729
    for group in range(19):
        for slot in range(2):
            index = group * 2 + slot
            searches.append({
                "id": f"g{group:02d}-s{slot}",
                "group": group,
                "slot": slot,
                "seed": seed_start + index * seed_step,
                "dense_hint": False,
                "support_hint": files["support_hint"] if slot else None,
                "randomize_search": True,
                "workers": 1,
                "seconds": 10800,
                "objective_upper_bound": 2252,
                "cascade_all_mixed_states": True,
                "memory_limit_mib": 5500,
            })
    payload = {
        "schema": "run-073-search-spec-v1",
        "run_id": "run-073",
        "solver_package": "ortools==9.15.6755",
        "physical_jobs": 19,
        "max_parallel": 19,
        "reserved_runner_slots": 1,
        "searches_per_job": 2,
        "total_searches": 38,
        "job_timeout_minutes": 210,
        "mixed_states": 6558,
        "objective": "37*pure_extra_count+fourth_entry_count",
        "objective_upper_bound": 2252,
        "files": files,
        "sha256": hashes,
        "searches": searches,
        "outcome_rule": {
            "FEASIBLE_or_OPTIMAL": "independent full replay required",
            "INFEASIBLE_or_UNKNOWN": "diagnostic only",
            "missing_or_identity_failure": "technical incompleteness",
        },
    }
    payload["canonical_spec_sha256"] = hashlib.sha256(canonical(payload)).hexdigest()
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
