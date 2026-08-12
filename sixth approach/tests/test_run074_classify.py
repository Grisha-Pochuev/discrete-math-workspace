#!/usr/bin/env python3
"""Exercise every terminal branch of the capacity classifier."""

from __future__ import annotations

from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from run074_classify import classify_observation


def classify(**changes):
    values = {
        "code": 0,
        "rows": 2,
        "max_rss": 1000,
        "max_cgroup": 1_000_000,
        "worker_log": "",
        "result": None,
        "result_exists": False,
        "monitor_guard": False,
    }
    values.update(changes)
    return classify_observation(**values)


def main() -> None:
    completed = classify(
        result_exists=True,
        result={
            "schema": "run-073-result-v1",
            "search_id": "calibration-s0",
            "solver_status": "UNKNOWN",
        },
    )
    assert completed["classification"] == "completed" and completed["accepted_diagnostic"]

    positive = classify(
        result_exists=True,
        result={
            "schema": "run-073-result-v1",
            "search_id": "calibration-s0",
            "solver_status": "FEASIBLE",
        },
    )
    assert positive["classification"] == "completed" and positive["scientific_result"]

    guarded = classify(code=1, worker_log="MemoryError: working-set guard exceeded")
    assert guarded["classification"] == "capacity_rejected_by_worker_guard"

    duration = classify(code=124)
    assert duration["classification"] == "duration_rejected_by_outer_guard"

    signalled = classify(code=143, monitor_guard=True)
    assert signalled["classification"] == "capacity_rejected_by_signal"

    unexplained = classify(code=143)
    assert unexplained["classification"] == "unexpected_technical_failure"

    malformed = classify(
        result_exists=True,
        result={"schema": "wrong", "search_id": "calibration-s0", "solver_status": "UNKNOWN"},
    )
    assert malformed["classification"] == "unexpected_technical_failure"
    assert "classification_error" in malformed


if __name__ == "__main__":
    main()
