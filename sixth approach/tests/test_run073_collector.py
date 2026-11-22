#!/usr/bin/env python3
"""Synthetic complete and missing-record collector contracts."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import shutil


ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "sixth approach/specs/run-073-search.json"


def main():
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    root = Path(__file__).resolve().parent / "run073-collector-contract"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir()
    try:
        inputs = root / "inputs"
        inputs.mkdir()
        for search in spec["searches"]:
            target = inputs / search["id"]
            target.mkdir()
            result = {
                "schema": "run-073-result-v1",
                "search_id": search["id"],
                "solver_status": "UNKNOWN",
                "random_seed": search["seed"],
                "randomize_search": search["randomize_search"],
                "objective_upper_bound": search["objective_upper_bound"],
                "cascade_all_mixed_states": search["cascade_all_mixed_states"],
                "dense_hint": search["dense_hint"],
                "support_hint_sha256": None,
                "best_objective_bound": 0.0,
                "solver_wall_seconds": 1.0,
                "peak_observed_working_set_mib": 100.0,
            }
            if search.get("support_hint"):
                import hashlib
                result["support_hint_sha256"] = hashlib.sha256((ROOT / search["support_hint"]).read_bytes()).hexdigest()
            target.joinpath("result.json").write_text(json.dumps(result), encoding="utf-8")
        archive = root / "archive"
        subprocess.run([
            sys.executable, str(ROOT / "sixth approach/run073_collect.py"),
            "--input-root", str(inputs), "--spec", str(SPEC), "--output-dir", str(archive),
            "--workflow-run", "73", "--source-sha", "0" * 40,
        ], check=True, stdout=subprocess.DEVNULL)
        summary = json.loads(archive.joinpath("summary.json").read_text(encoding="utf-8"))
        assert summary["technical_coverage"] == "38/38" and summary["statuses"] == {"UNKNOWN": 38}
        inputs.joinpath(spec["searches"][0]["id"], "result.json").unlink()
        failed = subprocess.run([
            sys.executable, str(ROOT / "sixth approach/run073_collect.py"),
            "--input-root", str(inputs), "--spec", str(SPEC), "--output-dir", str(root / "bad"),
            "--workflow-run", "74", "--source-sha", "0" * 40,
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        assert failed.returncode != 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
