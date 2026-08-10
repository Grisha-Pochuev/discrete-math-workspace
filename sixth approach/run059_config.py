#!/usr/bin/env python3
"""Validate run-059 input and resolve one neutral matrix cell."""

from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
from typing import Any


EXPECTED_CELLS = {
    "c3-s63": (3, 63),
    "c3-s64": (3, 64),
    "c9-s63": (9, 63),
    "c9-s64": (9, 64),
}


def load_and_verify(path: Path) -> dict[str, Any]:
    spec = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "schema_version": 1,
        "run_id": "run-059",
        "audit_run_id": "run-059-audit",
        "provider": "circleci",
        "trigger": "tag_push",
        "trigger_tag": "ci-run-059",
        "workflow": "short-pool-v1",
        "runner": "ubuntu-2404:current",
        "resource_class": "large",
        "jobs": 32,
        "max_concurrency": 30,
        "groups_per_cell": 8,
        "workers_per_job": 4,
        "shard_count": 32,
        "partition_bits": 5,
        "partition": "parity-log2-v1",
        "single_threaded_workers": True,
    }
    for key, value in expected.items():
        if spec.get(key) != value:
            raise ValueError(f"unexpected {key}: {spec.get(key)!r}")

    cells = spec.get("cells")
    if not isinstance(cells, list) or len(cells) != len(EXPECTED_CELLS):
        raise ValueError("unexpected cell count")
    seen: set[tuple[int, int]] = set()
    for cell in cells:
        key = (cell.get("case"), cell.get("support"))
        if key in seen:
            raise ValueError(f"duplicate cell: {key!r}")
        seen.add(key)
    if seen != set(EXPECTED_CELLS.values()):
        raise ValueError(f"unexpected cells: {sorted(seen)!r}")
    return spec


def resolve_cell(spec: dict[str, Any], name: str) -> dict[str, Any]:
    if name not in EXPECTED_CELLS:
        raise ValueError(f"invalid neutral cell: {name}")
    case_id, support = EXPECTED_CELLS[name]
    matches = [
        item
        for item in spec["cells"]
        if item["case"] == case_id and item["support"] == support
    ]
    if len(matches) != 1:
        raise ValueError(f"cell resolution failed: {name}")
    cell = matches[0]
    return {
        "RUN_ID": spec["run_id"],
        "AUDIT_RUN_ID": spec["audit_run_id"],
        "CASE_ID": case_id,
        "SUPPORT": support,
        "ORBIT": cell["orbit"],
        "MISSING_TYPE": cell["missing_type"],
        "SHARD_COUNT": spec["shard_count"],
        "WORKERS_PER_JOB": spec["workers_per_job"],
        "WORKER_SECONDS": spec["worker_seconds"],
        "WORKER_CAP": spec["worker_cap"],
        "WORKER_MEMORY_MIB": spec["worker_memory_mib"],
        "CHECKPOINT_EVERY": spec["checkpoint_every"],
        "CHECKPOINT_SECONDS": spec["checkpoint_seconds"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--verify", action="store_true")
    mode.add_argument("--cell", choices=sorted(EXPECTED_CELLS))
    args = parser.parse_args()

    spec = load_and_verify(args.spec)
    if args.verify:
        print(
            json.dumps(
                {
                    "run_id": spec["run_id"],
                    "cells": len(spec["cells"]),
                    "jobs": spec["jobs"],
                    "shards": len(spec["cells"]) * spec["shard_count"],
                },
                sort_keys=True,
            )
        )
        return 0

    values = resolve_cell(spec, args.cell)
    for key, value in values.items():
        print(f"{key}={shlex.quote(str(value))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
