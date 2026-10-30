#!/usr/bin/env python3
"""Validate immutable inputs and emit the physical job matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    if spec["schema"] != "run-073-search-spec-v1" or spec["run_id"] != "run-073":
        raise AssertionError("unexpected immutable specification")
    declared_spec_sha = spec.pop("canonical_spec_sha256")
    if hashlib.sha256(canonical(spec)).hexdigest() != declared_spec_sha:
        raise AssertionError("canonical specification digest mismatch")
    repo_root = args.spec.resolve().parents[2]
    for name, relative in spec["files"].items():
        if sha256(repo_root / relative) != spec["sha256"][name]:
            raise AssertionError(f"immutable file mismatch: {name}")
    if (spec["physical_jobs"], spec["max_parallel"], spec["reserved_runner_slots"]) != (19, 19, 1):
        raise AssertionError("physical allocation mismatch")
    if spec["searches_per_job"] != 2 or spec["total_searches"] != 38:
        raise AssertionError("two-process packing mismatch")
    if spec["objective_upper_bound"] != 2252 or spec["mixed_states"] != 6558:
        raise AssertionError("scientific target mismatch")
    groups = []
    seen_ids = set()
    seen_seeds = set()
    for group in range(19):
        searches = [item for item in spec["searches"] if item["group"] == group]
        if len(searches) != 2 or {item["slot"] for item in searches} != {0, 1}:
            raise AssertionError("group coverage mismatch")
        for item in searches:
            index = group * 2 + item["slot"]
            if item["id"] != f"g{group:02d}-s{item['slot']}":
                raise AssertionError("search identity mismatch")
            if item["seed"] != 1009 + index * 104729:
                raise AssertionError("search seed mismatch")
            if (item["seconds"], item["workers"], item["memory_limit_mib"]) != (10800, 1, 5500):
                raise AssertionError("search resource contract mismatch")
            if not item["randomize_search"] or not item["cascade_all_mixed_states"]:
                raise AssertionError("search mode mismatch")
            if item["objective_upper_bound"] != 2252 or item["dense_hint"]:
                raise AssertionError("search target or hint mismatch")
            expected_hint = spec["files"]["support_hint"] if item["slot"] else None
            if item["support_hint"] != expected_hint:
                raise AssertionError("support hint portfolio mismatch")
            seen_ids.add(item["id"])
            seen_seeds.add(item["seed"])
        groups.append({"group": group})
    if len(seen_ids) != 38 or len(seen_seeds) != 38:
        raise AssertionError("search portfolio is not unique")
    print(json.dumps({"include": groups}, separators=(",", ":")))


if __name__ == "__main__":
    main()
