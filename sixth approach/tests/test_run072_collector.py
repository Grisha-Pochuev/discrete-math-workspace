#!/usr/bin/env python3
"""Synthetic complete and missing-record tests for the run-072 collector."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import run072_contract as contract


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_gzip(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as stream:
            stream.write(contract.canonical_bytes(payload))


def seal(payload):
    payload["canonical_outcome_sha256"] = hashlib.sha256(
        contract.canonical_bytes(payload)
    ).hexdigest()
    return payload


def populate(root, spec):
    spec_sha = contract.sha256_file(ROOT / "specs" / "run-072-finite-events.json")
    for search in spec["searches"]:
        directory = root / search["id"]
        checkpoint = seal({
            "schema": "run-072-finite-events-checkpoint-v1",
            "spec_sha256": spec_sha,
            "input_sha256": spec["input_sha256"],
            "search": search,
            "added_clauses": [],
            "added_clause_count": 0,
            "last_status": "TIME_LIMIT",
            "rounds": 1,
        })
        checkpoint_path = directory / "checkpoint.json.gz"
        write_gzip(checkpoint_path, checkpoint)
        result = seal({
            "schema": "run-072-finite-events-result-v1",
            "evidence_level": "synthetic collector contract",
            "search": search,
            "status": "TIME_LIMIT",
            "rounds": 1,
            "elapsed_seconds": 0.01,
            "workers": 1,
            "memory_mib": spec["memory_mib_per_search"],
            "base_clause_count": 1887,
            "added_clause_count": 0,
            "total_clause_count": 1887,
            "last_solver": {"status": "UNKNOWN"},
            "solver_status_histogram": {"UNKNOWN": 1},
            "last_row_histogram": {},
            "last_threat_count": None,
            "last_selected_candidate_count": None,
            "spec_sha256": spec_sha,
            "input_sha256": spec["input_sha256"],
            "input_outcome_sha256": spec["input_outcome_sha256"],
            "contract_sha256": spec["source_hashes"]["run072_contract.py"],
            "worker_sha256": spec["source_hashes"]["run072_worker.py"],
            "checkpoint_file": checkpoint_path.name,
            "checkpoint_sha256": contract.sha256_file(checkpoint_path),
            "checkpoint_outcome_sha256": checkpoint["canonical_outcome_sha256"],
            "solver": "synthetic",
            "python": "synthetic",
            "scope_warning": "synthetic",
        })
        write_json(directory / "result.json", result)


def command(input_root, output_root):
    return [
        sys.executable, str(ROOT / "run072_collect.py"),
        "--input-root", str(input_root),
        "--spec", str(ROOT / "specs" / "run-072-finite-events.json"),
        "--output-dir", str(output_root),
        "--workflow-run", "synthetic",
        "--source-sha", "0" * 40,
    ]


def main():
    spec = json.loads((ROOT / "specs" / "run-072-finite-events.json").read_text(encoding="utf-8"))
    temporary = ROOT / "tests" / "_run072_collector"
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir()
    try:
        inputs = temporary / "inputs"
        populate(inputs, spec)
        accepted = temporary / "accepted"
        subprocess.run(command(inputs, accepted), check=True)
        summary = json.loads((accepted / "summary.json").read_text(encoding="utf-8"))
        assert summary["received_searches"] == 80
        assert summary["physical_jobs"] == 20
        assert summary["reserved_runner_slots"] == 0
        assert summary["status_histogram"] == {"TIME_LIMIT": 80}
        (inputs / "s079" / "result.json").unlink()
        rejected = subprocess.run(command(inputs, temporary / "rejected"), capture_output=True)
        assert rejected.returncode != 0
        assert b"missing search results" in rejected.stderr
    finally:
        shutil.rmtree(temporary)
    print(json.dumps({"status": "accepted", "complete": 80, "missing_rejected": True}, sort_keys=True))


if __name__ == "__main__":
    main()
