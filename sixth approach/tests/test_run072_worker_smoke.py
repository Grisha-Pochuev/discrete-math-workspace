#!/usr/bin/env python3
"""Exercise the production worker with its exact input and a tiny time cap."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def main():
    temporary = ROOT / "tests" / "_run072_smoke"
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir()
    try:
        output = temporary / "result.json"
        checkpoint = temporary / "checkpoint.json.gz"
        subprocess.run([
            sys.executable,
            str(ROOT / "run072_worker.py"),
            "--spec", str(ROOT / "specs" / "run-072-finite-events.json"),
            "--search-id", "s000",
            "--output", str(output),
            "--checkpoint", str(checkpoint),
            "--smoke",
        ], check=True)
        result = json.loads(output.read_text(encoding="utf-8"))
        with gzip.open(checkpoint, "rt", encoding="utf-8") as stream:
            saved = json.load(stream)
        assert result["schema"] == "run-072-finite-events-result-v1"
        assert result["search"]["id"] == "s000"
        assert result["workers"] == 1
        assert result["base_clause_count"] == 1887
        assert result["status"] in {"SURVIVOR", "TIME_LIMIT", "MODEL_INFEASIBLE"}
        assert saved["schema"] == "run-072-finite-events-checkpoint-v1"
        assert saved["search"] == result["search"]
        assert saved["last_status"] == result["status"]
        assert saved["added_clause_count"] == result["added_clause_count"]
    finally:
        shutil.rmtree(temporary)
    print(json.dumps({"status": "accepted", "production_worker": True}, sort_keys=True))


if __name__ == "__main__":
    main()
