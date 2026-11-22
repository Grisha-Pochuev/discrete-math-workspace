#!/usr/bin/env python3
"""Contract checks for the immutable run-072 input and partition."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import run072_contract as contract


def main():
    spec_path = ROOT / "specs" / "run-072-finite-events.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    assert spec["schema"] == "run-072-finite-events-v1"
    assert spec["physical_jobs"] == 20
    assert spec["reserved_runner_slots"] == 0
    assert spec["logical_workers_per_job"] == 4
    assert len(spec["searches"]) == 80
    assert len({item["id"] for item in spec["searches"]}) == 80
    assert len({item["seed"] for item in spec["searches"]}) == 80
    for group in range(20):
        searches = [item for item in spec["searches"] if item["group"] == group]
        assert [item["slot"] for item in searches] == [0, 1, 2, 3]
    for name, digest in spec["source_hashes"].items():
        assert contract.sha256_file(ROOT / name) == digest
    compact = contract.load_compact_input(
        spec["input_path"], spec["input_sha256"], spec["input_outcome_sha256"]
    )
    assert compact["source_clause_count"] == 325
    assert compact["learned_clause_count"] == 1562
    assert compact["total_clause_count"] == 1887
    candidates = contract.candidate_entries()
    forbidden, targets = contract.build_rows(candidates)
    rows = forbidden + targets
    for record in compact["learned_clauses"]:
        contract.validate_dynamic_clause(record, rows, len(candidates))
    print(json.dumps({
        "status": "accepted",
        "jobs": 20,
        "workers": 80,
        "clauses": 1887,
        "learned_rows_replayed": 1562,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
