#!/usr/bin/env python3
"""Strictly collect the complete neutral search portfolio."""

from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workflow-run", type=int, required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    expected = {item["id"]: item for item in spec["searches"]}
    found = {}
    for path in args.input_root.rglob("result.json"):
        result = json.loads(path.read_text(encoding="utf-8"))
        search_id = result.get("search_id")
        if search_id not in expected or search_id in found:
            raise AssertionError("missing identity or duplicate search result")
        found[search_id] = (path, result)
    if set(found) != set(expected):
        raise AssertionError(f"search coverage mismatch: {len(found)}/{len(expected)}")

    statuses = Counter()
    survivors_by_support = {}
    records = []
    repo_root = args.spec.resolve().parents[2]
    verifier = repo_root / spec["files"]["verifier"]
    types = repo_root / spec["files"]["types"]
    data = repo_root / spec["files"]["input"]
    acceptance = repo_root / spec["files"]["input_acceptance"]
    for search_id in sorted(expected):
        search = expected[search_id]
        path, result = found[search_id]
        required = {
            "random_seed": search["seed"],
            "randomize_search": search["randomize_search"],
            "objective_upper_bound": search["objective_upper_bound"],
            "cascade_all_mixed_states": search["cascade_all_mixed_states"],
            "dense_hint": search["dense_hint"],
        }
        if any(result.get(key) != value for key, value in required.items()):
            raise AssertionError(f"search configuration mismatch: {search_id}")
        expected_hint_sha = sha256(repo_root / search["support_hint"]) if search.get("support_hint") else None
        if result.get("support_hint_sha256") != expected_hint_sha:
            raise AssertionError(f"search hint identity mismatch: {search_id}")
        status = result["solver_status"]
        if status not in {"OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN"}:
            raise AssertionError(f"invalid terminal status: {search_id} {status}")
        statuses[status] += 1
        record = {
            "search_id": search_id,
            "status": status,
            "result_sha256": sha256(path),
            "objective": result.get("objective"),
            "best_objective_bound": result.get("best_objective_bound"),
            "solver_wall_seconds": result.get("solver_wall_seconds"),
            "peak_observed_working_set_mib": result.get("peak_observed_working_set_mib"),
        }
        if status in {"OPTIMAL", "FEASIBLE"}:
            verify_output = path.with_name("collector-acceptance.json")
            subprocess.run([
                sys.executable, str(verifier), "--types", str(types), "--manifest", str(data),
                "--manifest-acceptance", str(acceptance), "--probe", str(path),
                "--output", str(verify_output),
            ], check=True)
            verified = json.loads(verify_output.read_text(encoding="utf-8"))
            if not verified.get("accepted") or verified["probe_sha256"] != sha256(path):
                raise AssertionError(f"survivor replay mismatch: {search_id}")
            support = {
                "active_pure_extras": result["active_pure_extras"],
                "active_fourth_entries": result["active_fourth_entries"],
            }
            support_sha = hashlib.sha256(canonical(support)).hexdigest()
            if support_sha not in survivors_by_support:
                survivors_by_support[support_sha] = {
                    "support_sha256": support_sha,
                    "search_ids": [],
                    "result": result,
                    "acceptance": verified,
                }
            survivors_by_support[support_sha]["search_ids"].append(search_id)
            record["support_sha256"] = support_sha
            record["acceptance_sha256"] = sha256(verify_output)
        records.append(record)

    survivors = [survivors_by_support[key] for key in sorted(survivors_by_support)]

    args.output_dir.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(args.spec, args.output_dir / "spec.json")
    with gzip.open(args.output_dir / "records.json.gz", "wt", encoding="utf-8", newline="\n") as stream:
        json.dump(records, stream, indent=2, sort_keys=True)
        stream.write("\n")
    with gzip.open(args.output_dir / "survivors.json.gz", "wt", encoding="utf-8", newline="\n") as stream:
        json.dump(survivors, stream, indent=2, sort_keys=True)
        stream.write("\n")
    summary = {
        "schema": "run-073-summary-v1",
        "technical_coverage": f"{len(records)}/{len(expected)}",
        "statuses": dict(sorted(statuses.items())),
        "scientific_survivors": len(survivors),
        "negative_status_scope": "INFEASIBLE and UNKNOWN are diagnostic only",
    }
    provenance = {
        "schema": "run-073-provenance-v1",
        "workflow_run": args.workflow_run,
        "source_sha": args.source_sha,
        "spec_sha256": sha256(args.spec),
    }
    write_json(args.output_dir / "summary.json", summary)
    write_json(args.output_dir / "provenance.json", provenance)
    files = sorted(path for path in args.output_dir.iterdir() if path.is_file())
    (args.output_dir / "checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in files), encoding="ascii", newline="\n"
    )
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
