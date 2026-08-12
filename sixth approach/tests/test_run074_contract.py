#!/usr/bin/env python3
"""Contract checks for the single-process capacity calibration."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "sixth approach/specs/run-074-capacity-calibration.json"


def main() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "sixth approach/run074_contract.py"), "--spec", str(SPEC)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout) == {"accepted": True, "search_id": "calibration-s0"}
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    assert spec["physical_jobs"] == spec["max_parallel"] == spec["processes_per_job"] == 1
    assert spec["searches"][0]["seconds"] == 3600
    assert spec["outcome_rule"]["signal_137_or_143_with_high_memory_telemetry"] == "accepted capacity diagnosis only"


if __name__ == "__main__":
    main()
