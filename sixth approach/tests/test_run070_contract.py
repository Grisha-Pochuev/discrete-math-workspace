#!/usr/bin/env python3
"""Small deterministic contract checks for run-070."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import run070_contract as contract  # noqa: E402


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert contract.ACTIVE_VARIABLES == 324
    assert len(contract.MATCHINGS[(0,)]) == 15
    assert len(contract.MATCHINGS[(0, 1, 2)]) == 105
    assert len(set(contract.iter_row_keys())) == 29160
    representatives = contract.canonical_target_representatives()
    assert len(representatives) == 3 and len(set(representatives)) == 3
    assert all(len(item) == 4 for item in representatives)

    sparse = set(representatives[0])
    sparse.update(contract.target_monomials(1)[0])
    sparse.update(contract.target_monomials(2)[0])
    sparse_replay = contract.scan_support(sparse, threat_limit=4)
    assert all(value >= 1 for value in sparse_replay["target_counts"].values())
    assert sparse_replay["forbidden_histogram"]["unique"] > 0

    dense_replay = contract.validate_support(range(contract.ACTIVE_VARIABLES))
    assert dense_replay["accepted"]
    assert dense_replay["target_counts"] == {"0": 105, "1": 105, "2": 105}
    assert dense_replay["forbidden_histogram"] == {
        "zero": 0,
        "unique": 0,
        "multiple": 29157,
    }

    spec_path = ROOT / "specs" / "run-070-boundary-support.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    assert spec["schema"] == "run-070-boundary-support-v1"
    assert len(spec["searches"]) == 80
    assert {item["group"] for item in spec["searches"]} == set(range(20))
    assert all(sum(item["group"] == group for item in spec["searches"]) == 4 for group in range(20))
    for name, expected in spec["source_hashes"].items():
        assert sha256(ROOT / name) == expected
    print(json.dumps({"all_checks_pass": True, "rows": 29160, "active": 324, "spec_sha256": sha256(spec_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
