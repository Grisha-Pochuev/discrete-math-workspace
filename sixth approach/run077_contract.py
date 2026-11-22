#!/usr/bin/env python3
"""Validate the immutable neutral residue contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


EXPECTED = {
    "schema": "neutral-proof-residue-v1",
    "run_id": "run-077",
    "lower_bound": 5,
    "pair_condition_assertion_count": 24,
    "expected_variable_count": 217801,
    "expected_clause_count": 1268249,
    "expected_cnf_sha256": "75a424598feac97f9eead14f5de24268853822aa65546eac53cab75e85e04b82",
    "solver_package": "cadical=1.7.4-1",
    "worker_count": 4,
    "worker_seeds": [1, 2, 3, 4],
    "solver_seconds": 3600,
    "job_timeout_minutes": 75,
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(path):
    spec = json.loads(path.read_text(encoding="utf-8"))
    for key, value in EXPECTED.items():
        if spec.get(key) != value:
            raise ValueError(f"contract differs: {key}")
    if spec.get("lower_bound_acceptance_sha256") != "f18359704ea08325011656bb1fae73b6192422fd7d8caa3139ed40c6db0f71a2":
        raise ValueError("lower-bound theorem identity differs")
    return spec


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    args = parser.parse_args()
    validate(args.spec)
    print(json.dumps({
        "accepted": True,
        "spec_sha256": sha(args.spec),
        "expected_variable_count": EXPECTED["expected_variable_count"],
        "expected_clause_count": EXPECTED["expected_clause_count"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()

