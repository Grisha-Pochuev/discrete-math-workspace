#!/usr/bin/env python3
"""Merge a complete parent matrix with four refined replacement leaves."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from run061_validate_shard import validate_record
from run063_validate_refined import validate_refined


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_text_sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_text(encoding="utf-8").replace("\r\n", "\n").encode()
    ).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--base-spec", required=True, type=Path)
    parser.add_argument("--parent-root", required=True, type=Path)
    parser.add_argument("--refinement-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    rescue = json.loads(args.spec.read_text(encoding="utf-8"))
    base = json.loads(args.base_spec.read_text(encoding="utf-8"))
    assert base["run_id"] == rescue["parent"]["run_id"]
    assert canonical_text_sha256(args.base_spec) == rescue["parent"]["spec_sha256"]
    parent_key = (
        rescue["parent"]["graph_type"], rescue["parent"]["shard"]
    )

    records = []
    failures = []
    replaced_parent = None
    for graph in base["graphs"]:
        root = args.parent_root / graph["id"]
        for shard in range(base["shards_per_graph"]):
            try:
                record = validate_record(
                    base,
                    graph["type"],
                    shard,
                    root / f"shard-{shard}.json",
                    root / f"shard-{shard}.exit",
                )
                record["source"] = "parent"
                if (graph["type"], shard) == parent_key:
                    assert record["screen_state"] == "unknown"
                    assert record["technical_complete"] is False
                    replaced_parent = record
                else:
                    assert record["technical_complete"] is True
                    records.append(record)
            except Exception as error:
                failures.append({
                    "source": "parent",
                    "graph": graph["type"],
                    "shard": shard,
                    "error": f"{type(error).__name__}: {error}",
                })

    refinement_id = next(
        item["id"] for item in base["graphs"]
        if item["type"] == rescue["parent"]["graph_type"]
    )
    root = args.refinement_root / refinement_id
    for shard in rescue["refinement"]["child_shards"]:
        try:
            record = validate_refined(
                rescue,
                base,
                shard,
                root / f"shard-{shard}.json",
                root / f"shard-{shard}.exit",
            )
            assert record["technical_complete"] is True
            records.append(record)
        except Exception as error:
            failures.append({
                "source": "refinement",
                "graph": rescue["parent"]["graph_type"],
                "shard": shard,
                "error": f"{type(error).__name__}: {error}",
            })

    states = Counter(item["screen_state"] for item in records)
    complete_coverage = (
        replaced_parent is not None
        and len(records) == rescue["expected_leaf_shards"]
        and not failures
    )
    accepted = complete_coverage and all(
        item["technical_complete"] for item in records
    )
    report = {
        "schema_version": 1,
        "run_id": rescue["run_id"],
        "accepted": accepted,
        "technical_complete": accepted,
        "mathematical_closure": (
            accepted and states["infeasible"] == rescue["expected_leaf_shards"]
        ),
        "expected_leaf_shards": rescue["expected_leaf_shards"],
        "validated_leaf_shards": len(records),
        "states": dict(sorted(states.items())),
        "scientific_survivors": sum(
            item["scientific_survivor"] for item in records
        ),
        "solve_rounds": sum(item["solve_rounds"] for item in records),
        "wall_seconds_sum": sum(item["wall_seconds"] for item in records),
        "replaced_parent": replaced_parent,
        "failures": failures,
        "records": sorted(
            records, key=lambda item: (item["graph"], item["shard"], item["source"])
        ),
        "spec_sha256": canonical_text_sha256(args.spec),
        "base_spec_sha256": canonical_text_sha256(args.base_spec),
        "cut_bundle_sha256": rescue["cut_bundle_sha256"],
        "parent_workflow_run": rescue["parent"]["workflow_run"],
    }
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "accepted": accepted,
        "validated_leaf_shards": len(records),
        "states": report["states"],
        "scientific_survivors": report["scientific_survivors"],
        "failures": len(failures),
    }, sort_keys=True))
    if not accepted:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
