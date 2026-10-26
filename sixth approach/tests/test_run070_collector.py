#!/usr/bin/env python3
"""Synthetic complete-matrix test for the compact run-070 collector."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    spec_path = ROOT / "specs" / "run-070-boundary-support.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    contract_sha = sha256(ROOT / "run070_contract.py")
    fixed = os.environ.get("RUN070_TEST_ROOT")
    temporary_context = (
        tempfile.TemporaryDirectory(prefix="run070-collector-", dir=ROOT / "tests")
        if fixed is None
        else _FixedDirectory(fixed)
    )
    with temporary_context as temporary:
        temp = Path(temporary)
        inputs = temp / "inputs"
        for search in spec["searches"]:
            root = inputs / search["id"]
            root.mkdir(parents=True)
            result = {
                "schema": "run-070-boundary-support-result-v1",
                "search": search,
                "status": "TIME_LIMIT",
                "workers": 1,
                "spec_sha256": sha256(spec_path),
                "contract_sha256": contract_sha,
            }
            (root / "result.json").write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        archive = temp / "archive"
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "run070_collect.py"),
                "--input-root",
                str(inputs),
                "--spec",
                str(spec_path),
                "--output-dir",
                str(archive),
                "--workflow-run",
                "0",
                "--source-sha",
                "0" * 40,
            ],
            check=True,
        )
        assert {path.name for path in archive.iterdir()} == {
            "checksums.sha256",
            "input-spec.json",
            "results.json.gz",
            "summary.json",
            "survivors.json",
        }
        summary = json.loads((archive / "summary.json").read_text(encoding="utf-8"))
        assert summary["received_searches"] == 80
        assert summary["status_histogram"] == {"TIME_LIMIT": 80}
        assert summary["unique_survivors"] == 0
    print(json.dumps({"all_checks_pass": True, "synthetic_results": 80}, sort_keys=True))


class _FixedDirectory:
    def __init__(self, path):
        self.path = Path(path)

    def __enter__(self):
        if not self.path.is_dir() or any(self.path.iterdir()):
            raise RuntimeError("fixed test directory must exist and be empty")
        return str(self.path)

    def __exit__(self, exc_type, exc, traceback):
        return False


if __name__ == "__main__":
    main()
