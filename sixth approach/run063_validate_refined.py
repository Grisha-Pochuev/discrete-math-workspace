#!/usr/bin/env python3
"""Strict validator for one refined child of a single incomplete cell."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from run061_validate_shard import validate_record


def derived_worker_spec(rescue, base):
    graph = next(
        item for item in base["graphs"]
        if item["type"] == rescue["parent"]["graph_type"]
    )
    return {
        "run_id": rescue["run_id"],
        "graphs": [graph],
        "shards_per_graph": rescue["refinement"]["shard_count"],
        "partition": rescue["refinement"]["partition"],
        "partition_bits": rescue["refinement"]["partition_bits"],
        "workers_per_shard": rescue["workers_per_shard"],
        "exchange_rounds": rescue["exchange_rounds"],
        "seconds_per_round": rescue["seconds_per_round"],
        "worker_memory_mib": rescue["worker_memory_mib"],
        "exact_cut_version": rescue["exact_cut_version"],
        "cut_bundle_sha256": rescue["cut_bundle_sha256"],
    }


def validate_refined(rescue, base, shard, output_path, exit_path):
    assert shard in rescue["refinement"]["child_shards"]
    assert shard % rescue["parent"]["shard_count"] == rescue["parent"]["shard"]
    result = validate_record(
        derived_worker_spec(rescue, base),
        rescue["parent"]["graph_type"],
        shard,
        output_path,
        exit_path,
    )
    result["source"] = "refinement"
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--base-spec", required=True, type=Path)
    parser.add_argument("--shard", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--exit", required=True, dest="exit_path", type=Path)
    parser.add_argument("--validation", required=True, type=Path)
    args = parser.parse_args()
    rescue = json.loads(args.spec.read_text(encoding="utf-8"))
    base = json.loads(args.base_spec.read_text(encoding="utf-8"))
    result = validate_refined(
        rescue, base, args.shard, args.output, args.exit_path
    )
    assert result["technical_complete"], "refined child remains UNKNOWN"
    args.validation.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
