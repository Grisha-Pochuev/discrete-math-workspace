#!/usr/bin/env python3
"""Run a bounded positive production-worker and independent replay contract."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def main():
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT.parent / ".local-tools/ortools-runtime2")
    output = Path(__file__).resolve().parent / "run073-worker-contract-result.json"
    acceptance = Path(__file__).resolve().parent / "run073-worker-contract-acceptance.json"
    try:
        subprocess.run([
            sys.executable, str(ROOT / "sixth approach/run073_worker.py"),
            "--types", str(ROOT / "sixth approach/specs/run-073-types.json"),
            "--manifest", str(ROOT / "sixth approach/specs/run-073-input.json"),
            "--manifest-acceptance", str(ROOT / "sixth approach/specs/run-073-input-acceptance.json"),
            "--seconds", "20", "--workers", "1", "--random-seed", "1009",
            "--randomize-search", "--memory-limit-mib", "1500", "--fix-dense-support",
            "--cascade-aggregate-state", "515", "--output", str(output),
        ], check=True, stdout=subprocess.DEVNULL, env=environment)
        result = json.loads(output.read_text(encoding="utf-8"))
        assert result["solver_status"] in {"FEASIBLE", "OPTIMAL"}
        subprocess.run([
            sys.executable, str(ROOT / "sixth approach/run073_verify.py"),
            "--types", str(ROOT / "sixth approach/specs/run-073-types.json"),
            "--manifest", str(ROOT / "sixth approach/specs/run-073-input.json"),
            "--manifest-acceptance", str(ROOT / "sixth approach/specs/run-073-input-acceptance.json"),
            "--probe", str(output), "--output", str(acceptance),
        ], check=True, stdout=subprocess.DEVNULL, env=environment)
        assert json.loads(acceptance.read_text(encoding="utf-8"))["accepted"]
    finally:
        output.unlink(missing_ok=True)
        acceptance.unlink(missing_ok=True)
        output.with_name(output.name + ".tmp").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
