#!/usr/bin/env python3
"""Synthetic complete-coverage test for the run-071 collector."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
SIXTH = HERE.parent
SPEC = SIXTH / "specs" / "run-071-boundary-event.json"
COLLECTOR = SIXTH / "run071_collect.py"
CONTRACT = SIXTH / "run070_contract.py"
WORKER = SIXTH / "run071_worker.py"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="run071-collector-") as temporary:
        root = Path(temporary)
        inputs = root / "inputs"
        archive = root / "archive"
        for search in spec["searches"]:
            directory = inputs / search["id"]
            directory.mkdir(parents=True)
            result = {
                "schema": "run-071-boundary-event-result-v1",
                "evidence_level": "synthetic",
                "search": search,
                "status": "TIME_LIMIT",
                "rounds": 1,
                "dynamic_cuts": 0,
                "exact_event_cuts": 2,
                "elapsed_seconds": 0.01,
                "workers": 1,
                "memory_mib": spec["memory_mib_per_search"],
                "solver": "synthetic",
                "python": sys.version.split()[0],
                "spec_sha256": sha256(SPEC),
                "contract_sha256": sha256(CONTRACT),
                "worker_sha256": sha256(WORKER),
                "event_cut_sha256": sha256(Path(spec["event_cut_path"])),
                "solver_stats": {},
                "scope_warning": "synthetic",
            }
            (directory / "result.json").write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )
        subprocess.run([
            sys.executable,
            str(COLLECTOR),
            "--input-root", str(inputs),
            "--spec", str(SPEC),
            "--output-dir", str(archive),
            "--workflow-run", "synthetic-071",
            "--source-sha", "0" * 40,
        ], cwd=SIXTH.parent, check=True)
        summary = json.loads((archive / "summary.json").read_text(encoding="utf-8"))
        assert summary["received_searches"] == 72
        assert summary["physical_jobs"] == 18
        assert summary["reserved_runner_slots"] == 2
        assert summary["status_histogram"] == {"TIME_LIMIT": 72}
        assert summary["scientific_status"] == "bounded_search_incomplete"
        assert json.loads((archive / "survivors.json").read_text(encoding="utf-8")) == []
        with gzip.open(archive / "results.json.gz", "rt", encoding="utf-8") as stream:
            assert len(json.load(stream)) == 72
        manifest = (archive / "checksums.sha256").read_text(encoding="ascii").splitlines()
        assert len(manifest) == 5
    print(json.dumps({"accepted": True, "records": 72}, sort_keys=True))


if __name__ == "__main__":
    main()
