#!/usr/bin/env python3
"""Small negative contract tests for the calibration package."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path

import run076_contract as contract


HERE = Path(__file__).resolve().parents[1]


def main():
    source_path = HERE / "specs" / "run-076-input.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    assert len(source["classes"]) == 10
    assert sum(record["support_orbits"] for record in source["classes"]) == 179
    assert sum(record["support_placements"] for record in source["classes"]) == 42504
    broken = json.loads(json.dumps(source))
    broken["classes"][1]["support_orbits"] += 1
    broken_sha = hashlib.sha256(json.dumps(broken, sort_keys=True).encode()).hexdigest()
    source_sha = hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest()
    assert broken_sha != source_sha
    print(json.dumps({"accepted": True, "negative_mutation_detected": True}, sort_keys=True))


if __name__ == "__main__":
    main()
