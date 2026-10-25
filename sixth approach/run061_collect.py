#!/usr/bin/env python3
"""Collect all exact-cut adaptive shards and preserve every final survivor."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from run061_validate_shard import validate_record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--input-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))

    records = []
    failures = []
    for graph in spec["graphs"]:
        for shard in range(spec["shards_per_graph"]):
            root = args.input_root / graph["id"]
            try:
                records.append(validate_record(
                    spec,
                    graph["type"],
                    shard,
                    root / f"shard-{shard}.json",
                    root / f"shard-{shard}.exit",
                ))
            except Exception as error:
                failures.append({
                    "graph": graph["type"],
                    "shard": shard,
                    "error": f"{type(error).__name__}: {error}",
                })

    states = Counter(item["screen_state"] for item in records)
    complete_coverage = len(records) == spec["jobs"] and not failures
    technical_complete = (
        complete_coverage and all(item["technical_complete"] for item in records)
    )
    report = {
        "schema_version": 1,
        "run_id": spec["run_id"],
        "accepted": technical_complete,
        "technical_complete": technical_complete,
        "mathematical_closure": technical_complete and states["infeasible"] == spec["jobs"],
        "expected_shards": spec["jobs"],
        "validated_shards": len(records),
        "states": dict(sorted(states.items())),
        "scientific_survivors": sum(item["scientific_survivor"] for item in records),
        "solve_rounds": sum(item["solve_rounds"] for item in records),
        "wall_seconds_sum": sum(item["wall_seconds"] for item in records),
        "failures": failures,
        "records": records,
        "spec_sha256": hashlib.sha256(args.spec.read_bytes()).hexdigest(),
        "cut_bundle_sha256": spec["cut_bundle_sha256"],
    }
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "accepted": report["accepted"],
        "mathematical_closure": report["mathematical_closure"],
        "validated_shards": report["validated_shards"],
        "states": report["states"],
        "scientific_survivors": report["scientific_survivors"],
        "failures": len(failures),
    }, sort_keys=True))
    if not report["accepted"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
