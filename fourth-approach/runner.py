#!/usr/bin/env python3
"""Checkpointed task runner for Fourth approach."""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
import traceback
from pathlib import Path

from canonicalize import process_stage1_shard, write_gzip_json
from inventory import inventory_git_tree_shard
from schema import APPROACH, read_json, validate_spec


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--run-index", type=int, required=True)
    parser.add_argument("--shard-id", type=int, required=True)
    parser.add_argument("--shard-count", type=int, required=True)
    parser.add_argument("--seconds", type=int, required=True)
    parser.add_argument("--max-attempts", type=int, default=0)
    parser.add_argument("--output", required=True)
    parser.add_argument("--source-ref", default="HEAD")
    args = parser.parse_args()

    started = time.time()
    repo = Path(args.repo).resolve()
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "manifest.json"
    result_path = out / "records.json.gz"
    status = "TECHNICAL_FAILURE"
    errors: list[str] = []
    metrics: dict = {}
    controlled_non_result = False

    launch_status = {
        "schema_version": 1,
        "approach": APPROACH,
        "task": args.task,
        "run_index": args.run_index,
        "shard_id": args.shard_id,
        "shard_count": args.shard_count,
        "source_ref": args.source_ref,
        "seconds": args.seconds,
        "max_attempts": args.max_attempts,
        "started_at": started,
        "pid": os.getpid(),
        "python": sys.version,
        "platform": platform.platform(),
    }
    atomic_json(out / "launch-status.json", launch_status)

    try:
        spec = validate_spec(read_json(args.spec), require_ready=True)
        if spec["task"] != args.task or int(spec["run_index"]) != args.run_index:
            raise ValueError("runner arguments disagree with run specification")
        if not 0 <= args.shard_id < args.shard_count:
            raise ValueError("invalid shard coordinates")
        if args.seconds < 30:
            raise ValueError("seconds must be at least 30")

        if args.task == "stage0_source_inventory":
            result = inventory_git_tree_shard(
                repo,
                spec,
                args.shard_id,
                args.shard_count,
                ref=args.source_ref,
            )
        elif args.task == "stage1_canonicalize_verify":
            result = process_stage1_shard(
                repo,
                spec,
                args.shard_id,
                args.shard_count,
                seconds=args.seconds,
                max_attempts=args.max_attempts,
            )
            controlled_non_result = not bool(result.get("complete", False))
        else:
            raise ValueError(f"unsupported task: {args.task}")
        write_gzip_json(result_path, result)
        metrics = dict(result.get("metrics", {}))
        status = "SUCCESS" if not controlled_non_result else "BOUNDED_INCOMPLETE"
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
        (out / "traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
    finally:
        finished = time.time()
        manifest = {
            "schema_version": 1,
            "approach": APPROACH,
            "task": args.task,
            "run_index": args.run_index,
            "shard_id": args.shard_id,
            "shard_count": args.shard_count,
            "source_ref": args.source_ref,
            "status": status,
            "controlled_non_result": controlled_non_result,
            "errors": errors,
            "metrics": metrics,
            "started_at": started,
            "finished_at": finished,
            "elapsed_seconds": finished - started,
            "result_file": result_path.name if result_path.exists() else None,
            "result_bytes": result_path.stat().st_size if result_path.exists() else 0,
        }
        atomic_json(manifest_path, manifest)
    return 0 if status in {"SUCCESS", "BOUNDED_INCOMPLETE"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
