#!/usr/bin/env python3
"""Strict technical collector for the neutral native frontier probe."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate_record(record, *, run_id, spec_sha, pattern, target, shard, shards):
    require(record["schema"] == "run083-native-frontier-v1", "schema mismatch")
    require(record["run_id"] == run_id, "run identity mismatch")
    require(record["spec_sha256"] == spec_sha, "spec identity mismatch")
    require(record["pattern"] == pattern, "pattern mismatch")
    require(record["target_size"] == target, "target-size mismatch")
    require(record["shard_id"] == shard, "shard-id mismatch")
    require(record["shard_count"] == shards, "shard-count mismatch")
    require(record["complete"] is True, "incomplete worker record")
    require(record["stopped_reason"] == "complete", "nonterminal worker reason")
    require(
        record["processed_base_orbits"] == record["assigned_base_orbits"],
        "base-orbit coverage mismatch",
    )
    require(record["visited_states"] > 0, "empty state traversal")
    require(record["frontier_count"] == sum(record["outcome_counts"].values()),
            "outcome partition mismatch")
    for text in record["open_support_masks"]:
        value = int(text)
        require(value > 0 and value.bit_count() == target, "invalid open support mask")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("calibration", "full"), required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--github-run", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    spec = load(args.spec)
    spec_sha = sha256(args.spec)
    require(spec["schema"] == "run083-native-frontier-spec-v1", "spec schema mismatch")
    run_id = spec["run_id"]
    files = sorted(args.input_dir.rglob("*.json"))
    require(files, "no worker records found")

    records = []
    checksums = {}
    if args.mode == "calibration":
        expected = {
            "111": spec["calibration"]["expected"]["111"],
            "21": spec["calibration"]["expected"]["21"],
        }
        require(len(files) == 2, "calibration requires exactly two records")
        seen = set()
        for path in files:
            record = load(path)
            pattern = record["pattern"]
            require(pattern in expected and pattern not in seen, "calibration pattern coverage")
            seen.add(pattern)
            validate_record(
                record,
                run_id=run_id,
                spec_sha=spec_sha,
                pattern=pattern,
                target=spec["calibration"]["target_size"],
                shard=0,
                shards=1,
            )
            contract = expected[pattern]
            require(record["base_orbit_count"] == contract["base_orbit_count"],
                    "base count regression")
            require(record["frontier_count"] == contract["frontier_count"],
                    "frontier regression")
            require(record["outcome_counts"] == contract["outcome_counts"],
                    "lattice outcome regression")
            require(record["open_support_masks"] == [], "calibration unexpectedly open")
            checksums[path.name] = sha256(path)
            records.append(record)
        require(seen == set(expected), "missing calibration pattern")
    else:
        shards = spec["full"]["logical_shards_per_pattern"]
        require(len(files) == len(spec["patterns"]) * shards,
                "full record-count mismatch")
        coverage = set()
        for path in files:
            record = load(path)
            key = (record["pattern"], record["shard_id"])
            require(record["pattern"] in spec["patterns"], "unknown pattern")
            require(key not in coverage, "duplicate logical shard")
            coverage.add(key)
            validate_record(
                record,
                run_id=run_id,
                spec_sha=spec_sha,
                pattern=record["pattern"],
                target=spec["full"]["target_size"],
                shard=record["shard_id"],
                shards=shards,
            )
            checksums[path.name] = sha256(path)
            records.append(record)
        expected_coverage = {
            (pattern, shard)
            for pattern in spec["patterns"]
            for shard in range(shards)
        }
        require(coverage == expected_coverage, "logical shard coverage mismatch")

    aggregate_outcomes = {}
    open_supports = {pattern: set() for pattern in spec["patterns"]}
    for record in records:
        pattern = record["pattern"]
        aggregate_outcomes.setdefault(pattern, {})
        for outcome, count in record["outcome_counts"].items():
            aggregate_outcomes[pattern][outcome] = (
                aggregate_outcomes[pattern].get(outcome, 0) + count
            )
        open_supports[pattern].update(record["open_support_masks"])

    payload = {
        "schema": "run083-native-frontier-collector-v1",
        "mode": args.mode,
        "run_id": run_id,
        "github_run": str(args.github_run),
        "source_sha": args.source_sha,
        "spec_sha256": spec_sha,
        "worker_record_count": len(records),
        "technical_complete": True,
        "aggregate_raw_outcome_counts": aggregate_outcomes,
        "worker_catalogue": [
            {
                "pattern": record["pattern"],
                "shard_id": record["shard_id"],
                "shard_count": record["shard_count"],
                "assigned_base_orbits": record["assigned_base_orbits"],
                "processed_base_orbits": record["processed_base_orbits"],
                "visited_states": record["visited_states"],
                "frontier_count": record["frontier_count"],
                "outcome_counts": record["outcome_counts"],
                "open_support_count": len(record["open_support_masks"]),
            }
            for record in sorted(records, key=lambda item: (item["pattern"], item["shard_id"]))
        ],
        "scientific_open_supports": {
            pattern: sorted(values, key=int) for pattern, values in open_supports.items()
        },
        "scientific_open_support_count": sum(map(len, open_supports.values())),
        "worker_checksums": dict(sorted(checksums.items())),
        "scope_boundary": (
            "calibration is a native regression; full zero-open output remains exploratory "
            "until a separate certificate extractor and independent semantic intake accept it"
        ),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload["canonical_outcome_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(rendered, encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({
        "written": str(args.output),
        "technical_complete": True,
        "scientific_open_support_count": payload["scientific_open_support_count"],
        "canonical_outcome_sha256": payload["canonical_outcome_sha256"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
