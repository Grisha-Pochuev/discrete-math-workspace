#!/usr/bin/env python3
"""Short production-path smoke test for one run-071 worker."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
SIXTH = HERE.parent
ROOT = SIXTH.parent
SOURCE = SIXTH / "specs" / "run-071-boundary-event.json"
SMOKE_SPEC = HERE / "_run071_smoke_spec.json"
SMOKE_RESULT = HERE / "_run071_smoke_result.json"


def main():
    spec = json.loads(SOURCE.read_text(encoding="utf-8"))
    spec["seconds_per_search"] = 8
    spec["seconds_per_round"] = 3
    spec["max_rounds"] = 1
    spec["cuts_per_round"] = 16
    try:
        SMOKE_SPEC.write_text(
            json.dumps(spec, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        subprocess.run([
            sys.executable,
            str(SIXTH / "run071_worker.py"),
            "--spec", str(SMOKE_SPEC),
            "--search-id", "s080",
            "--output", str(SMOKE_RESULT),
        ], cwd=ROOT, check=True, timeout=20)
        result = json.loads(SMOKE_RESULT.read_text(encoding="utf-8"))
        assert result["schema"] == "run-071-boundary-event-result-v1"
        assert result["search"]["id"] == "s080"
        assert result["workers"] == 1
        assert result["exact_event_cuts"] == 2
        assert result["status"] in {"SURVIVOR", "TIME_LIMIT", "MODEL_INFEASIBLE"}
        print(json.dumps({
            "accepted": True,
            "status": result["status"],
            "rounds": result["rounds"],
        }, sort_keys=True))
    finally:
        SMOKE_RESULT.unlink(missing_ok=True)
        SMOKE_SPEC.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
