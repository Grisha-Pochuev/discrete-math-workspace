#!/usr/bin/env python3
"""Pack one provider group's compact per-orbit outcomes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--group", type=int, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec = load(args.spec)
    source = load(args.input)
    if re.fullmatch(r"[0-9a-f]{40}", args.source_sha) is None:
        raise ValueError("source SHA is malformed")
    if not 0 <= args.group < spec["group_count"]:
        raise ValueError("group outside specification")
    expected = sorted(
        orbit for assignment in spec["assignments"] if assignment["group"] == args.group
        for orbit in assignment["orbit_ids"]
    )
    input_by_id = {record["orbit_id"]: record for record in source["orbits"]}
    records = []
    for orbit_id in expected:
        directory = args.raw / f"orbit-{orbit_id}"
        metadata_path = directory / "metadata.json"
        exit_path = directory / "solver.exit"
        log_path = directory / "solver.log"
        if not metadata_path.is_file() or not exit_path.is_file() or not log_path.is_file():
            raise ValueError(f"orbit {orbit_id} transport record is incomplete")
        metadata = load(metadata_path)
        if (
            metadata.get("schema") != "neutral-cnf-metadata-v1"
            or metadata.get("orbit_id") != orbit_id
            or metadata.get("orbit_size") != input_by_id[orbit_id]["orbit_size"]
            or metadata.get("catalogue_sha256") != spec["catalogue_sha256"]
        ):
            raise ValueError(f"orbit {orbit_id} metadata identity differs")
        if metadata.get("variable_count", 0) <= 144 or metadata.get("clause_count", 0) <= 0:
            raise ValueError(f"orbit {orbit_id} formula dimensions are malformed")
        if re.fullmatch(r"[0-9a-f]{64}", metadata.get("cnf_sha256", "")) is None:
            raise ValueError(f"orbit {orbit_id} CNF hash is malformed")
        code = int(exit_path.read_text(encoding="utf-8").strip())
        if code == 10:
            status = "SAT"
        elif code == 20:
            status = "UNSAT_DIAGNOSTIC"
        elif code in (124, 137, 143):
            status = "TIMEOUT" if code == 124 else "SIGNAL"
        else:
            status = "ERROR"
        record = {
            "orbit_id": orbit_id,
            "orbit_size": input_by_id[orbit_id]["orbit_size"],
            "partition": input_by_id[orbit_id]["partition"],
            "status": status,
            "solver_exit": code,
            "variable_count": metadata["variable_count"],
            "clause_count": metadata["clause_count"],
            "cnf_sha256": metadata["cnf_sha256"],
            "solver_log_sha256": sha(log_path),
        }
        if status == "SAT":
            positive_path = directory / "positive.json"
            if not positive_path.is_file():
                raise ValueError(f"SAT orbit {orbit_id} lacks replayed positive support")
            positive = load(positive_path)
            if positive.get("orbit_id") != orbit_id or not positive.get("direct_replay_accepted"):
                raise ValueError(f"SAT orbit {orbit_id} positive support differs")
            record["positive_support"] = positive
        records.append(record)
    payload = {
        "schema": "neutral-bounded-orbit-group-v1",
        "group": args.group,
        "source_sha": args.source_sha,
        "spec_sha256": sha(args.spec),
        "input_sha256": sha(args.input),
        "records": records,
    }
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"group": args.group, "record_count": len(records)}, sort_keys=True))


if __name__ == "__main__":
    main()
