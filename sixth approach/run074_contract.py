#!/usr/bin/env python3
"""Validate the immutable single-process capacity calibration contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def lf_bytes(path: Path) -> bytes:
    """Return the canonical LF bytes stored by Git and checked out on Linux."""
    return path.read_bytes().replace(b"\r\n", b"\n")


def sha256(path: Path) -> str:
    return hashlib.sha256(lf_bytes(path)).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    args = parser.parse_args()

    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    if spec.get("schema") != "run-074-capacity-calibration-v1" or spec.get("run_id") != "run-074":
        raise AssertionError("unexpected immutable specification")
    declared_spec_sha = spec.pop("canonical_spec_sha256")
    if hashlib.sha256(canonical(spec)).hexdigest() != declared_spec_sha:
        raise AssertionError("canonical specification digest mismatch")

    repo_root = args.spec.resolve().parents[2]
    if set(spec["files"]) != set(spec["sha256"]):
        raise AssertionError("immutable file map mismatch")
    for name, relative in spec["files"].items():
        if sha256(repo_root / relative) != spec["sha256"][name]:
            raise AssertionError(f"immutable file mismatch: {name}")

    if (spec["physical_jobs"], spec["max_parallel"], spec["processes_per_job"]) != (1, 1, 1):
        raise AssertionError("single-process allocation mismatch")
    if spec["job_timeout_minutes"] != 90 or spec["telemetry_period_seconds"] != 10:
        raise AssertionError("calibration timing mismatch")
    if spec["mixed_states"] != 6558 or spec["objective_upper_bound"] != 2252:
        raise AssertionError("scientific target mismatch")

    searches = spec.get("searches", [])
    if len(searches) != 1:
        raise AssertionError("calibration must contain exactly one search")
    search = searches[0]
    if search.get("id") != "calibration-s0":
        raise AssertionError("calibration identity mismatch")
    expected = {
        "seconds": 3600,
        "workers": 1,
        "memory_limit_mib": 8500,
        "seed": 105738,
        "objective_upper_bound": 2252,
        "randomize_search": True,
        "cascade_all_mixed_states": True,
        "dense_hint": False,
        "support_hint": spec["files"]["support_hint"],
    }
    for key, value in expected.items():
        if search.get(key) != value:
            raise AssertionError(f"calibration search mismatch: {key}")

    print(json.dumps({"accepted": True, "search_id": search["id"]}, separators=(",", ":")))


if __name__ == "__main__":
    main()
