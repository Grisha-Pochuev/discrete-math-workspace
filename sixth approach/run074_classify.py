#!/usr/bin/env python3
"""Classify one instrumented capacity-calibration outcome."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


RESULT_STATES = {"OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN"}


def telemetry(path: Path) -> tuple[int, int, int]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "utc\tpython_rss_kib\tcgroup_current_bytes\tmem_available_kib":
        raise AssertionError("malformed telemetry header")
    rows = []
    for line in lines[1:]:
        fields = line.split("\t")
        if len(fields) != 4:
            raise AssertionError("malformed telemetry row")
        rows.append((fields[0], *(int(value) for value in fields[1:])))
    return (
        len(rows),
        max((row[1] for row in rows), default=0),
        max((row[2] for row in rows), default=0),
    )


def classify_observation(
    *,
    code: int,
    rows: int,
    max_rss: int,
    max_cgroup: int,
    worker_log: str,
    result: dict[str, object] | None,
    result_exists: bool,
    monitor_guard: bool,
) -> dict[str, object]:
    summary: dict[str, object] = {
        "schema": "run-074-capacity-result-v1",
        "worker_exit": code,
        "telemetry_rows": rows,
        "max_python_rss_kib": max_rss,
        "max_cgroup_current_bytes": max_cgroup,
        "classification": "unexpected_technical_failure",
        "scientific_result": False,
        "accepted_diagnostic": False,
    }
    try:
        if code == 0 and result_exists and result is not None:
            status = result.get("solver_status")
            if result.get("schema") != "run-073-result-v1":
                raise AssertionError("malformed worker result schema")
            if result.get("search_id") != "calibration-s0" or status not in RESULT_STATES:
                raise AssertionError("malformed worker result identity or state")
            summary["classification"] = "completed"
            summary["solver_status"] = status
            summary["scientific_result"] = status in {"OPTIMAL", "FEASIBLE"}
            summary["accepted_diagnostic"] = status in {"INFEASIBLE", "UNKNOWN"}
        elif (
            code == 1
            and not result_exists
            and "working-set guard exceeded" in worker_log
            and rows >= 2
        ):
            summary["classification"] = "capacity_rejected_by_worker_guard"
            summary["accepted_diagnostic"] = True
        elif code == 124 and not result_exists and rows >= 2:
            summary["classification"] = "duration_rejected_by_outer_guard"
            summary["accepted_diagnostic"] = True
        elif (
            code in {137, 143}
            and not result_exists
            and rows >= 2
            and (
                monitor_guard
                or max_rss >= 7 * 1024 * 1024
                or max_cgroup >= 11 * 1024 * 1024 * 1024
            )
        ):
            summary["classification"] = "capacity_rejected_by_signal"
            summary["accepted_diagnostic"] = True
    except (AssertionError, json.JSONDecodeError, OSError, TypeError, ValueError) as error:
        summary["classification_error"] = f"{type(error).__name__}: {error}"
    return summary


def classify(root: Path) -> dict[str, object]:
    rows, max_rss, max_cgroup = telemetry(root / "telemetry.tsv")
    result_path = root / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.is_file() else None
    return classify_observation(
        code=int((root / "worker.exit").read_text(encoding="ascii").strip()),
        rows=rows,
        max_rss=max_rss,
        max_cgroup=max_cgroup,
        worker_log=(root / "worker.log").read_text(encoding="utf-8", errors="replace"),
        result=result,
        result_exists=result_path.is_file(),
        monitor_guard=(root / "monitor-guard.log").is_file(),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    summary = classify(args.input)
    (args.input / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    if summary["classification"] == "unexpected_technical_failure":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
