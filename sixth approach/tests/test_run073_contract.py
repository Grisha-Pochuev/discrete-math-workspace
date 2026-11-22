#!/usr/bin/env python3
"""Contract tests for the neutral two-process portfolio."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "sixth approach/specs/run-073-search.json"


def main():
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    completed = subprocess.run([
        sys.executable, str(ROOT / "sixth approach/run073_contract.py"), "--spec", str(SPEC)
    ], check=True, capture_output=True, text=True)
    matrix = json.loads(completed.stdout)
    assert len(matrix["include"]) == 19
    assert spec["max_parallel"] == 19 and spec["reserved_runner_slots"] == 1
    assert len(spec["searches"]) == 38
    assert len({item["seed"] for item in spec["searches"]}) == 38
    assert all(item["workers"] == 1 and item["seconds"] == 10800 for item in spec["searches"])
    assert all(item["objective_upper_bound"] == 2252 for item in spec["searches"])
    assert all(item["cascade_all_mixed_states"] for item in spec["searches"])
    for group in range(19):
        rows = [item for item in spec["searches"] if item["group"] == group]
        assert len(rows) == 2
        assert not rows[0]["support_hint"] and rows[1]["support_hint"]


if __name__ == "__main__":
    main()
