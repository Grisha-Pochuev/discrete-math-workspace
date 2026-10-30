#!/usr/bin/env python3
"""Collect, replay, and compact all run-070 search records."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

import run070_contract as contract


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workflow-run", required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()

    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    if spec["schema"] != "run-070-boundary-support-v1" or len(spec["searches"]) != 80:
        raise ValueError("wrong immutable spec")
    expected = {item["id"]: item for item in spec["searches"]}
    results = []
    seen = set()
    contract_path = Path(__file__).with_name("run070_contract.py")
    for path in sorted(args.input_root.rglob("result.json")):
        result = json.loads(path.read_text(encoding="utf-8"))
        if result["schema"] != "run-070-boundary-support-result-v1":
            raise ValueError(f"wrong result schema at {path}")
        search_id = result["search"]["id"]
        if search_id not in expected or search_id in seen:
            raise ValueError(f"unexpected or duplicate search {search_id}")
        seen.add(search_id)
        if result["search"] != expected[search_id]:
            raise ValueError(f"search identity mismatch for {search_id}")
        if result["spec_sha256"] != sha256(args.spec):
            raise ValueError(f"spec identity mismatch for {search_id}")
        if result["contract_sha256"] != sha256(contract_path):
            raise ValueError(f"contract identity mismatch for {search_id}")
        if result["workers"] != 1 or result["status"] not in {
            "SURVIVOR", "TIME_LIMIT", "MODEL_INFEASIBLE"
        }:
            raise ValueError(f"invalid terminal record for {search_id}")
        results.append(result)
    missing = sorted(set(expected) - seen)
    if missing:
        raise ValueError(f"missing search results: {missing}")

    survivor_map = {}
    for result in results:
        if result["status"] != "SURVIVOR":
            continue
        active = result["selected_active"]
        if active != sorted(set(active)) or any(
            not 0 <= index < contract.ACTIVE_VARIABLES for index in active
        ):
            raise ValueError("invalid active support")
        digest = hashlib.sha256(json.dumps(active, separators=(",", ":")).encode()).hexdigest()
        if digest != result["selected_sha256"]:
            raise ValueError("support hash mismatch")
        replay = contract.validate_support(active)
        if not replay["accepted"] or replay != result["exact_replay"]:
            raise ValueError("survivor replay mismatch")
        survivor_map.setdefault(
            digest,
            {
                "selected_sha256": digest,
                "selected_count": len(active),
                "selected_active": active,
                "search_ids": [],
                "exact_replay": replay,
            },
        )["search_ids"].append(result["search"]["id"])

    results.sort(key=lambda item: item["search"]["id"])
    survivors = sorted(survivor_map.values(), key=lambda item: (item["selected_count"], item["selected_sha256"]))
    histogram = Counter(item["status"] for item in results)
    if survivors:
        scientific_status = "support_survivors_found"
    elif histogram.get("TIME_LIMIT"):
        scientific_status = "bounded_search_incomplete"
    else:
        scientific_status = "no_survivor_without_portable_refutation"

    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "schema": "run-070-boundary-support-collection-v1",
        "evidence_level": "exact survivor replay; all negative statuses diagnostic",
        "workflow_run": str(args.workflow_run),
        "source_sha": args.source_sha,
        "spec_sha256": sha256(args.spec),
        "contract_sha256": sha256(contract_path),
        "expected_searches": 80,
        "received_searches": len(results),
        "physical_jobs": 20,
        "independent_single_thread_workers_per_job": 4,
        "status_histogram": dict(sorted(histogram.items())),
        "scientific_status": scientific_status,
        "unique_survivors": len(survivors),
        "minimum_survivor_support": min((item["selected_count"] for item in survivors), default=None),
        "scope_warning": "Support survivors only satisfy a necessary cancellation condition and still require exact coefficient analysis.",
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.output_dir / "survivors.json").write_text(
        json.dumps(survivors, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    payload = (json.dumps(results, sort_keys=True, separators=(",", ":")) + "\n").encode()
    with (args.output_dir / "results.json.gz").open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as stream:
            stream.write(payload)
    shutil.copyfile(args.spec, args.output_dir / "input-spec.json")
    files = [
        args.output_dir / "summary.json",
        args.output_dir / "survivors.json",
        args.output_dir / "results.json.gz",
        args.output_dir / "input-spec.json",
    ]
    (args.output_dir / "checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in files), encoding="ascii"
    )
    print(json.dumps({"status": scientific_status, "survivors": len(survivors), "histogram": dict(histogram)}, sort_keys=True))


if __name__ == "__main__":
    main()
