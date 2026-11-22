#!/usr/bin/env python3
"""Strictly collect, replay, and compact all run-072 records."""

from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import shutil

import run072_contract as contract


def read_gzip(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def write_gzip(path, payload):
    with Path(path).open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as stream:
            stream.write(contract.canonical_bytes(payload))


def canonical_outcome(payload):
    copy = dict(payload)
    claimed = copy.pop("canonical_outcome_sha256")
    if hashlib.sha256(contract.canonical_bytes(copy)).hexdigest() != claimed:
        raise ValueError("canonical outcome mismatch")
    return claimed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workflow-run", required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()

    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    if (
        spec.get("schema") != "run-072-finite-events-v1"
        or spec.get("physical_jobs") != 20
        or spec.get("reserved_runner_slots") != 0
        or spec.get("logical_workers_per_job") != 4
        or len(spec.get("searches", [])) != 80
    ):
        raise ValueError("wrong immutable spec")
    spec_sha256 = contract.sha256_file(args.spec)
    source_root = Path(__file__).resolve().parent
    for name, digest in spec["source_hashes"].items():
        if contract.sha256_file(source_root / name) != digest:
            raise ValueError(f"source identity mismatch: {name}")
    compact = contract.load_compact_input(
        spec["input_path"], spec["input_sha256"], spec["input_outcome_sha256"]
    )
    expected = {item["id"]: item for item in spec["searches"]}
    results = []
    additions = {}
    survivor_records = []
    seen = set()
    candidates = None
    forbidden_rows = target_rows = rows = None
    base_keys = {
        contract.clause_key(item["required"], item["alternatives"])
        for item in compact["source_clauses"] + compact["learned_clauses"]
    }
    for result_path in sorted(args.input_root.rglob("result.json")):
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if result.get("schema") != "run-072-finite-events-result-v1":
            raise ValueError(f"wrong result schema: {result_path}")
        canonical_outcome(result)
        search_id = result["search"]["id"]
        if search_id not in expected or search_id in seen:
            raise ValueError(f"unexpected or duplicate search: {search_id}")
        seen.add(search_id)
        if (
            result["search"] != expected[search_id]
            or result["status"] not in {"SURVIVOR", "TIME_LIMIT", "MODEL_INFEASIBLE"}
            or result["workers"] != 1
            or result["spec_sha256"] != spec_sha256
            or result["input_sha256"] != spec["input_sha256"]
            or result["input_outcome_sha256"] != spec["input_outcome_sha256"]
            or result["contract_sha256"] != spec["source_hashes"]["run072_contract.py"]
            or result["worker_sha256"] != spec["source_hashes"]["run072_worker.py"]
            or result["base_clause_count"] != compact["total_clause_count"]
        ):
            raise ValueError(f"result identity mismatch: {search_id}")
        checkpoint_path = result_path.with_name(result["checkpoint_file"])
        if contract.sha256_file(checkpoint_path) != result["checkpoint_sha256"]:
            raise ValueError(f"checkpoint hash mismatch: {search_id}")
        checkpoint = read_gzip(checkpoint_path)
        if (
            checkpoint.get("schema") != "run-072-finite-events-checkpoint-v1"
            or canonical_outcome(checkpoint) != result["checkpoint_outcome_sha256"]
            or checkpoint["spec_sha256"] != spec_sha256
            or checkpoint["input_sha256"] != spec["input_sha256"]
            or checkpoint["search"] != expected[search_id]
            or checkpoint["last_status"] != result["status"]
            or checkpoint["added_clause_count"] != result["added_clause_count"]
            or len(checkpoint["added_clauses"]) != result["added_clause_count"]
        ):
            raise ValueError(f"checkpoint contract mismatch: {search_id}")
        if checkpoint["added_clauses"]:
            if rows is None:
                candidates = contract.candidate_entries()
                forbidden_rows, target_rows = contract.build_rows(candidates)
                rows = forbidden_rows + target_rows
            for record in checkpoint["added_clauses"]:
                contract.validate_dynamic_clause(record, rows, len(candidates))
                key = contract.clause_key(record["required"], record["alternatives"])
                if key in base_keys:
                    raise ValueError(f"base clause repeated: {search_id}")
                entry = additions.setdefault(key, {**record, "search_ids": []})
                entry["search_ids"].append(search_id)
        if result["status"] == "SURVIVOR":
            survivor_path = result_path.with_name(result["survivor_file"])
            if contract.sha256_file(survivor_path) != result["survivor_sha256"]:
                raise ValueError(f"survivor hash mismatch: {search_id}")
            survivor = json.loads(survivor_path.read_text(encoding="utf-8"))
            if canonical_outcome(survivor) != result["survivor_outcome_sha256"]:
                raise ValueError(f"survivor outcome mismatch: {search_id}")
            if rows is None:
                candidates = contract.candidate_entries()
                forbidden_rows, target_rows = contract.build_rows(candidates)
                rows = forbidden_rows + target_rows
            support = sum(1 << index for index in survivor["selected_indices"])
            replay = contract.exact_survivor_payload(
                support, candidates, forbidden_rows, target_rows
            )
            if replay != survivor:
                raise ValueError(f"survivor replay mismatch: {search_id}")
            survivor_records.append({"search_id": search_id, **survivor})
        results.append(result)
    missing = sorted(set(expected) - seen)
    if missing:
        raise ValueError(f"missing search results: {missing}")

    histogram = Counter(result["status"] for result in results)
    scientific_status = (
        "finite_survivors_found" if survivor_records
        else "bounded_search_incomplete" if histogram.get("TIME_LIMIT")
        else "no_survivor_without_portable_refutation"
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results.sort(key=lambda item: item["search"]["id"])
    survivor_records.sort(key=lambda item: (item["selected_count"], item["search_id"]))
    merged_additions = sorted(
        additions.values(),
        key=lambda item: contract.clause_key(item["required"], item["alternatives"]),
    )
    summary = {
        "schema": "run-072-finite-events-collection-v1",
        "evidence_level": "strict 80-record coverage and independent exact survivor/clause replay",
        "workflow_run": str(args.workflow_run),
        "source_sha": args.source_sha,
        "spec_sha256": spec_sha256,
        "input_sha256": spec["input_sha256"],
        "input_outcome_sha256": spec["input_outcome_sha256"],
        "base_clause_count": compact["total_clause_count"],
        "unique_added_clause_count": len(merged_additions),
        "expected_searches": 80,
        "received_searches": len(results),
        "physical_jobs": 20,
        "reserved_runner_slots": 0,
        "independent_single_thread_workers_per_job": 4,
        "status_histogram": dict(sorted(histogram.items())),
        "scientific_status": scientific_status,
        "survivor_records": len(survivor_records),
        "scope_warning": "Negative bounded statuses are diagnostic; only exact survivors and replayed clauses are retained.",
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    (args.output_dir / "survivors.json").write_text(
        json.dumps(survivor_records, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    write_gzip(args.output_dir / "results.json.gz", results)
    write_gzip(args.output_dir / "learned-delta.json.gz", merged_additions)
    shutil.copyfile(args.spec, args.output_dir / "input-spec.json")
    files = [
        args.output_dir / "summary.json",
        args.output_dir / "survivors.json",
        args.output_dir / "results.json.gz",
        args.output_dir / "learned-delta.json.gz",
        args.output_dir / "input-spec.json",
    ]
    (args.output_dir / "checksums.sha256").write_text(
        "".join(f"{contract.sha256_file(path)}  {path.name}\n" for path in files),
        encoding="ascii", newline="\n",
    )
    print(json.dumps({
        "status": scientific_status,
        "histogram": dict(histogram),
        "survivors": len(survivor_records),
        "unique_added_clauses": len(merged_additions),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
