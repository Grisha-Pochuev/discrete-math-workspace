#!/usr/bin/env python3
"""Validate the immutable neutral bounded-scan specification."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--header", type=Path, required=True)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    source = json.loads(args.input.read_text(encoding="utf-8"))
    if spec.get("schema") != "neutral-bounded-orbit-scan-spec-v1":
        raise ValueError("wrong spec schema")
    claimed = spec.pop("canonical_sha256", None)
    if claimed != hashlib.sha256(canonical(spec)).hexdigest():
        raise ValueError("spec canonical hash mismatch")
    if source.get("schema") != "neutral-bounded-orbit-input-v1":
        raise ValueError("wrong input schema")
    source_claimed = source.pop("canonical_sha256", None)
    if source_claimed != hashlib.sha256(canonical(source)).hexdigest():
        raise ValueError("input canonical hash mismatch")
    if spec["input_file_sha256"] != sha(args.input) or spec["worker_header_sha256"] != sha(args.header):
        raise ValueError("spec file identity mismatch")
    worker = args.header.with_name("run075_worker.cpp")
    if not worker.is_file() or spec.get("worker_source_sha256") != sha(worker):
        raise ValueError("worker source identity mismatch")
    if spec["input_canonical_sha256"] != source_claimed:
        raise ValueError("spec/input canonical identity mismatch")
    if source["source_catalogue_sha256"] != spec["catalogue_sha256"]:
        raise ValueError("catalogue identity mismatch")
    if source["source_catalogue_acceptance_canonical_sha256"] != spec["catalogue_acceptance_canonical_sha256"]:
        raise ValueError("catalogue acceptance identity mismatch")
    if source["orbit_count"] != 179 or [record["orbit_id"] for record in source["orbits"]] != list(range(179)):
        raise ValueError("immutable input orbit identities differ")
    if spec["group_count"] != 19 or spec["max_parallel"] != 19 or spec["lanes_per_group"] != 4:
        raise ValueError("provider allocation contract differs")
    assignments = spec["assignments"]
    if len(assignments) != 76:
        raise ValueError("assignment lane count differs")
    for index, record in enumerate(assignments):
        if record["group"] != index // 4 or record["lane"] != index % 4:
            raise ValueError("lane identity differs")
        if not 2 <= len(record["orbit_ids"]) <= 3:
            raise ValueError("lane load is outside calibrated bounds")
    coverage = [orbit for record in assignments for orbit in record["orbit_ids"]]
    if sorted(coverage) != list(range(1, 179)) or len(coverage) != len(set(coverage)):
        raise ValueError("missing or duplicate orbit assignment")
    if spec["solver"] != {"name": "cadical", "ubuntu_package_version": "1.7.4-1", "seconds_per_orbit": 180}:
        raise ValueError("solver contract differs")
    if spec["reference_contract"] != {
        "orbit_id": 1,
        "variable_count": 168328,
        "clause_count": 980520,
        "dimacs_sha256": "fb7eb15f7c1669e8695cf355263c64387a3effcf58d0e37da8050c1a9220a686",
    }:
        raise ValueError("reference contract differs")
    print(json.dumps({"accepted": True, "canonical_sha256": claimed, "coverage": len(coverage)}, sort_keys=True))


if __name__ == "__main__":
    main()
