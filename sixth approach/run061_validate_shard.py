#!/usr/bin/env python3
"""Strict structural validator for one exact-cut adaptive shard."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def graph_record(spec, graph):
    records = [item for item in spec["graphs"] if item["type"] == graph]
    assert len(records) == 1
    return records[0]


def validate_record(spec, graph, shard, output_path: Path, exit_path: Path):
    expected_graph = graph_record(spec, graph)
    assert output_path.is_file(), output_path
    assert exit_path.is_file(), exit_path
    exit_code = int(exit_path.read_text(encoding="utf-8").strip())
    assert exit_code in (0, 2)
    record = json.loads(output_path.read_text(encoding="utf-8"))

    assert record["schema_version"] == 1
    assert record["run_id"] == spec["run_id"]
    assert record["graph"] == graph
    assert record["shard_id"] == shard
    assert record["shard_count"] == spec["shards_per_graph"]
    assert record["partition"] == spec["partition"]
    assert record["workers"] == spec["workers_per_shard"]
    assert record["requested_exchange_rounds"] == spec["exchange_rounds"]
    assert record["seconds_per_round"] == spec["seconds_per_round"]
    assert record["memory_mib"] == spec["worker_memory_mib"]
    assert record["exact_cut_version"] == spec["exact_cut_version"]
    assert record["exact_event_cut_bundle_sha256"] == spec["cut_bundle_sha256"]
    assert record["exact_event_cuts"] == expected_graph["exact_event_cuts"]
    assert record["exact_event_cut_literals"] == expected_graph["exact_event_cut_literals"]
    assert record["perfect_matchings"] == expected_graph["expected_matchings"]
    assert record["mixed_rows"] == 6558
    assert record["term_variables"] == 6558 * expected_graph["expected_matchings"]
    assert record["support_variables"] == 180
    assert record["anchor_variables"] == 120
    assert record["anchor_support_variables"] == 72
    assert record["noncoordinate_variables"] == 24
    assert record["assignment_variables"] == 120
    assert record["assignment_column_variables"] == 240
    assert len(record["round_statuses"]) == record["solve_rounds"]
    assert len(record["round_wall_seconds"]) == record["solve_rounds"]
    assert 1 <= record["solve_rounds"] <= spec["exchange_rounds"] + 1

    if exit_code == 2:
        assert record["status"] == "UNKNOWN"
        assert record["screen_state"] == "unknown"
    else:
        assert record["status"] in ("OPTIMAL", "FEASIBLE", "INFEASIBLE")
        assert record["screen_state"] in (
            "infeasible", "exchange_clean_candidate", "rejected_candidate"
        )

    feasible_states = ("exchange_clean_candidate", "rejected_candidate")
    if record["screen_state"] in feasible_states:
        masks = record["support_masks"]
        assert len(masks) == 20
        assert all(0 < mask < 512 for mask in masks)
        for bit in range(spec["partition_bits"]):
            assert bool(masks[0] & (1 << bit)) == bool((shard >> bit) & 1)
        assert sum(mask.bit_count() for mask in masks) == record["active_entries"]
        assert len(record["anchors"]) == 24
        assert record["noncoordinate_anchors"] >= 1
        assert sum(item["noncoordinate"] for item in record["anchors"]) == record["noncoordinate_anchors"]
        assert len(record["assignments"]) == record["noncoordinate_anchors"]
        assert sum(record["matching_histogram"].values()) == 6558
        assert record["matching_histogram"].get("1", 0) == 0
        if record["screen_state"] == "exchange_clean_candidate":
            assert record["direct_exchange_contradictions"] == 0
        else:
            assert record["direct_exchange_contradictions"] > 0
            assert record["solve_rounds"] == spec["exchange_rounds"] + 1
    else:
        assert record["direct_exchange_contradictions"] == 0

    return {
        "graph": graph,
        "shard": shard,
        "exit_code": exit_code,
        "status": record["status"],
        "screen_state": record["screen_state"],
        "solve_rounds": record["solve_rounds"],
        "wall_seconds": record["wall_seconds"],
        "technical_complete": record["screen_state"] != "unknown",
        "scientific_survivor": record["screen_state"] in feasible_states,
        "sha256": sha256(output_path),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--graph", required=True)
    parser.add_argument("--shard", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--exit", required=True, dest="exit_path", type=Path)
    parser.add_argument("--validation", required=True, type=Path)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    result = validate_record(
        spec, args.graph, args.shard, args.output, args.exit_path
    )
    args.validation.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
