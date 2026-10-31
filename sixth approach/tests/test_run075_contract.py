#!/usr/bin/env python3
"""Small mutation tests for the neutral bounded-scan contract."""

from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]


def main():
    spec = json.loads((HERE / "specs" / "run-075-bounded-orbits.json").read_text(encoding="utf-8"))
    coverage = [orbit for record in spec["assignments"] for orbit in record["orbit_ids"]]
    assert spec["group_count"] == spec["max_parallel"] == 19
    assert spec["lanes_per_group"] == 4
    assert sorted(coverage) == list(range(1, 179))
    assert len(coverage) == len(set(coverage))
    assert {len(record["orbit_ids"]) for record in spec["assignments"]} == {2, 3}
    assert spec["outcome_contract"]["UNSAT"].startswith("diagnostic only")
    print("run075 contract tests: accepted")


if __name__ == "__main__":
    main()
