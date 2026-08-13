#!/usr/bin/env python3
"""Validate the immutable neutral calibration contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


EXPECTED = [
    ([0, 0, 0, 5], 1, 24, True),
    ([0, 0, 1, 4], 6, 360, False),
    ([0, 0, 2, 3], 18, 1200, False),
    ([0, 1, 0, 4], 6, 720, False),
    ([0, 1, 1, 3], 16, 5760, False),
    ([0, 1, 2, 2], 27, 5400, False),
    ([0, 2, 0, 3], 18, 2400, False),
    ([0, 2, 1, 2], 45, 10800, False),
    ([0, 3, 1, 1], 12, 2880, False),
    ([1, 1, 1, 2], 30, 12960, False),
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    source = json.loads(args.input.read_text(encoding="utf-8"))
    if spec.get("schema") != "neutral-proof-calibration-v1" or source.get("schema") != "neutral-proof-class-input-v1":
        raise ValueError("wrong contract schema")
    if spec["input_sha256"] != sha(args.input):
        raise ValueError("input hash differs")
    if spec["class_id"] != 1 or spec["expected_cnf_sha256"] != "9c9af19de20cc648b4beaa9bdb15b6f23ee7259bef694bcbcb8708d4b2a3ccc8":
        raise ValueError("calibration identity differs")
    if len(source.get("classes", [])) != 10:
        raise ValueError("class count differs")
    observed = []
    for expected_id, record in enumerate(source["classes"]):
        if record["class_id"] != expected_id:
            raise ValueError("noncanonical class ids")
        observed.append((record["counts"], record["support_orbits"], record["support_placements"], record["already_certified"]))
    if observed != EXPECTED:
        raise ValueError("immutable class table differs")
    if sum(record["support_orbits"] for record in source["classes"]) != 179:
        raise ValueError("support orbit coverage differs")
    if sum(record["support_placements"] for record in source["classes"]) != 42504:
        raise ValueError("support placement coverage differs")
    print(json.dumps({"accepted": True, "class_count": 10, "calibration_class": 1, "input_sha256": sha(args.input)}, sort_keys=True))


if __name__ == "__main__":
    main()
