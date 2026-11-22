#!/usr/bin/env python3
"""Dependency-free synthetic contract checks for the neutral cube scan."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile


def load_module(path):
    spec = importlib.util.spec_from_file_location("run079_cube_scan", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--temporary-root", type=Path)
    args = parser.parse_args()
    module = load_module(args.script.resolve())
    spec = module.load_spec(args.spec.resolve())
    temporary = (
        args.temporary_root.resolve()
        if args.temporary_root is not None
        else Path(tempfile.mkdtemp(prefix="run079-synthetic-"))
    )
    temporary.mkdir(parents=True, exist_ok=True)
    try:
        root = temporary / "results"
        for lane in range(spec["lane_count"]):
            records = [
                {
                    "cube_id": cube_id,
                    "cube_literals": list(module.cube_literals(spec, cube_id)),
                    "solver_exit": 20,
                    "wall_seconds": 0.01,
                    "solver_output_tail": "s UNSATISFIABLE\n",
                    "state": "UNSAT_UNCERTIFIED",
                }
                for cube_id in module.lane_cubes(spec, lane)
            ]
            payload = module.lane_payload(spec, lane, records, True)
            path = root / f"group-{lane // 4}" / f"lane-{lane:03d}" / "result.json"
            module.atomic_json(path, payload)
            module.validate_lane(spec, payload, lane)
        output = temporary / "compact"
        collect_args = argparse.Namespace(
            spec=args.spec.resolve(),
            input_root=root,
            output_dir=output,
            workflow_run="synthetic",
            source_sha="0" * 40,
        )
        module.command_collect(collect_args)
        summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
        if (
            summary.get("technical_complete") is not True
            or summary.get("conclusion") != "UNCERTIFIED_UNSAT_SCAN"
            or summary.get("record_count") != spec["cube_count"]
            or summary.get("state_histogram")
            != {"UNSAT_UNCERTIFIED": spec["cube_count"]}
        ):
            raise AssertionError("complete synthetic collection was rejected")

        first = json.loads(
            (root / "group-0" / "lane-000" / "result.json").read_text(
                encoding="utf-8"
            )
        )
        first["records"][0]["solver_exit"] = 10
        first = module.seal(first)
        try:
            module.validate_lane(spec, first, 0)
        except ValueError:
            pass
        else:
            raise AssertionError("state/exit mismatch was accepted")
        print(json.dumps({
            "accepted": True,
            "synthetic_cubes": spec["cube_count"],
            "synthetic_lanes": spec["lane_count"],
            "state_exit_mismatch_rejected": True,
        }, sort_keys=True))
    finally:
        shutil.rmtree(temporary, ignore_errors=True)
        parent = temporary.parent
        if parent.name == "smoke" and parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()


if __name__ == "__main__":
    main()
