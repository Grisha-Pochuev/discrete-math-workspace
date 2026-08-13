#!/usr/bin/env python3
"""Strictly collect a complete neutral bounded scan."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--groups", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec = load(args.spec)
    source = load(args.input)
    expected = {record["orbit_id"]: record for record in source["orbits"] if record["orbit_id"] != 0}
    files = sorted(args.groups.glob("group-*.json"))
    if len(files) != spec["group_count"]:
        raise ValueError(f"expected {spec['group_count']} group records, found {len(files)}")
    groups = []
    records = []
    group_ids = set()
    source_shas = set()
    for path in files:
        group = load(path)
        if group.get("schema") != "neutral-bounded-orbit-group-v1":
            raise ValueError(f"wrong group schema: {path}")
        if group.get("spec_sha256") != sha(args.spec) or group.get("input_sha256") != sha(args.input):
            raise ValueError(f"group identity mismatch: {path}")
        group_id = group.get("group")
        if not isinstance(group_id, int) or not 0 <= group_id < spec["group_count"] or group_id in group_ids:
            raise ValueError("missing, duplicate, or invalid group id")
        group_ids.add(group_id)
        source_sha = group.get("source_sha")
        if re.fullmatch(r"[0-9a-f]{40}", source_sha or "") is None:
            raise ValueError(f"group source identity is malformed: {path}")
        source_shas.add(source_sha)
        expected_orbits = sorted(
            orbit for assignment in spec["assignments"] if assignment["group"] == group_id
            for orbit in assignment["orbit_ids"]
        )
        actual_orbits = sorted(record["orbit_id"] for record in group.get("records", []))
        if actual_orbits != expected_orbits or len(actual_orbits) != len(set(actual_orbits)):
            raise ValueError(f"group {group_id} coverage differs")
        groups.append({"group": group_id, "file_sha256": sha(path), "record_count": len(actual_orbits)})
        records.extend(group["records"])
    if group_ids != set(range(spec["group_count"])):
        raise ValueError("group coverage differs")
    if len(source_shas) != 1:
        raise ValueError("groups came from differing source revisions")
    if sorted(record["orbit_id"] for record in records) != sorted(expected):
        raise ValueError("global orbit coverage differs")

    histogram = {}
    survivors = []
    technical_incomplete = []
    for record in records:
        orbit_id = record["orbit_id"]
        if record.get("orbit_size") != expected[orbit_id]["orbit_size"] or record.get("partition") != expected[orbit_id]["partition"]:
            raise ValueError(f"orbit metadata mismatch for {orbit_id}")
        status = record.get("status")
        if (
            not isinstance(record.get("variable_count"), int)
            or record["variable_count"] <= 144
            or not isinstance(record.get("clause_count"), int)
            or record["clause_count"] <= 0
            or re.fullmatch(r"[0-9a-f]{64}", record.get("cnf_sha256", "")) is None
            or re.fullmatch(r"[0-9a-f]{64}", record.get("solver_log_sha256", "")) is None
        ):
            raise ValueError(f"orbit formula identity is malformed for {orbit_id}")
        histogram[status] = histogram.get(status, 0) + 1
        if status == "SAT":
            support = record.get("positive_support")
            if not isinstance(support, dict) or support.get("orbit_id") != orbit_id or not support.get("direct_replay_accepted"):
                raise ValueError(f"SAT orbit {orbit_id} lacks replayed support")
            masks = support.get("cross_edge_masks")
            expected_edges = [[left, right] for left in range(4) for right in range(4, 8)]
            if (
                support.get("catalogue_sha256") != spec["catalogue_sha256"]
                or not isinstance(masks, list)
                or [item.get("edge") for item in masks] != expected_edges
                or any(not 0 < item.get("mask", 0) < 512 for item in masks)
            ):
                raise ValueError(f"SAT orbit {orbit_id} has malformed masks")
            survivors.append(support)
        elif status == "UNSAT_DIAGNOSTIC":
            if record.get("solver_exit") != 20:
                raise ValueError(f"UNSAT orbit {orbit_id} has wrong exit code")
        elif status in {"TIMEOUT", "SIGNAL", "ERROR", "UNKNOWN"}:
            technical_incomplete.append(record)
        else:
            raise ValueError(f"unknown status for orbit {orbit_id}: {status}")

    payload = {
        "schema": "neutral-bounded-orbit-collector-v1",
        "accepted_technical_coverage": not technical_incomplete,
        "negative_statuses_promoted_to_theorem": False,
        "spec_sha256": sha(args.spec),
        "input_sha256": sha(args.input),
        "source_sha": next(iter(source_shas)),
        "group_count": len(groups),
        "orbit_count": len(records),
        "status_histogram": dict(sorted(histogram.items())),
        "scientific_survivor_count": len(survivors),
        "scientific_survivors": survivors,
        "records": sorted(records, key=lambda item: item["orbit_id"]),
        "technical_incomplete": technical_incomplete,
        "groups": sorted(groups, key=lambda item: item["group"]),
        "scope": "complete diagnostic scan; UNSAT is not theorem evidence",
    }
    payload["canonical_sha256"] = hashlib.sha256(canonical(payload)).hexdigest()
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({key: value for key, value in payload.items() if key not in {"scientific_survivors", "records", "technical_incomplete", "groups"}}, sort_keys=True))
    if technical_incomplete:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
