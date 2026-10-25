#!/usr/bin/env python3
"""Strict collector for the neutral adaptive-screen worker."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--graph", required=True)
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    assert spec["run_id"] == args.run_id
    graph_record = next(item for item in spec["graphs"] if item["type"] == args.graph)
    assert spec["shards_per_job"] == 4
    assert spec["partition"] == "first-edge-bits-v1"
    assert spec["single_threaded_workers"] is True

    records = []
    hashes = {}
    for shard in range(4):
        output_path = args.input_dir / f"shard-{shard}.json"
        exit_path = args.input_dir / f"shard-{shard}.exit"
        assert output_path.is_file(), output_path
        assert exit_path.is_file(), exit_path
        exit_code = int(exit_path.read_text(encoding="utf-8").strip())
        record = json.loads(output_path.read_text(encoding="utf-8"))
        assert exit_code in (0, 2)
        assert record["schema_version"] == 1
        assert record["run_id"] == args.run_id
        assert record["graph"] == args.graph
        assert record["shard_id"] == shard
        assert record["shard_count"] == 4
        assert record["partition"] == spec["partition"]
        assert record["workers"] == 1
        assert record["requested_exchange_rounds"] == spec["exchange_rounds"]
        assert record["seconds_per_round"] == spec["seconds_per_round"]
        assert record["memory_mib"] == spec["worker_memory_mib"]
        assert record["perfect_matchings"] == graph_record["expected_matchings"]
        assert record["mixed_rows"] == 6558
        assert record["term_variables"] == 6558 * graph_record["expected_matchings"]
        assert record["support_variables"] == 180
        assert record["anchor_variables"] == 120
        assert record["anchor_support_variables"] == 72
        assert record["noncoordinate_variables"] == 24
        assert record["assignment_variables"] == 120
        assert record["assignment_column_variables"] == 240
        assert len(record["round_statuses"]) == record["solve_rounds"]
        assert len(record["round_wall_seconds"]) == record["solve_rounds"]
        if exit_code == 2:
            assert record["status"] == "UNKNOWN"
            assert record["screen_state"] == "unknown"
        else:
            assert record["status"] in ("OPTIMAL", "FEASIBLE", "INFEASIBLE")
            assert record["screen_state"] in (
                "infeasible", "exchange_clean_candidate", "rejected_candidate"
            )

        if record["screen_state"] in ("exchange_clean_candidate", "rejected_candidate"):
            masks = record["support_masks"]
            assert len(masks) == 20
            assert all(0 < mask < 512 for mask in masks)
            assert (masks[0] & 1 != 0) == bool(shard & 1)
            assert (masks[0] & 2 != 0) == bool((shard >> 1) & 1)
            assert sum(mask.bit_count() for mask in masks) == record["active_entries"]
            assert len(record["anchors"]) == 24
            assert record["noncoordinate_anchors"] >= 1
            assert sum(item["noncoordinate"] for item in record["anchors"]) == record["noncoordinate_anchors"]
            assert len(record["assignments"]) == record["noncoordinate_anchors"]
            assert sum(record["matching_histogram"].values()) == 6558
            if record["screen_state"] == "exchange_clean_candidate":
                assert record["direct_exchange_contradictions"] == 0
            else:
                assert record["direct_exchange_contradictions"] > 0
        else:
            assert record["direct_exchange_contradictions"] == 0

        records.append(record)
        hashes[output_path.name] = sha256(output_path)

    states = [record["screen_state"] for record in records]
    summary = {
        "schema_version": 1,
        "run_id": args.run_id,
        "graph": args.graph,
        "shards": 4,
        "partition": spec["partition"],
        "technical_complete": all(state != "unknown" for state in states),
        "all_shards_infeasible": all(state == "infeasible" for state in states),
        "infeasible_shards": states.count("infeasible"),
        "exchange_clean_shards": states.count("exchange_clean_candidate"),
        "round_limited_rejected_shards": states.count("rejected_candidate"),
        "unknown_shards": states.count("unknown"),
        "solve_rounds": sum(record["solve_rounds"] for record in records),
        "wall_seconds_sum": sum(record["wall_seconds"] for record in records),
        "learned_binomial_events": sum(record["learned_binomial_events"] for record in records),
        "learned_trinomial_events": sum(record["learned_trinomial_events"] for record in records),
        "final_direct_exchange_contradictions": sum(record["direct_exchange_contradictions"] for record in records),
        "sha256": hashes,
    }
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
