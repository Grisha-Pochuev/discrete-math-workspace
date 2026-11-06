#!/usr/bin/env python3
"""Synthetic acceptance and rejection tests for the strict collector."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parents[1]
SPEC = HERE / "specs" / "run-075-bounded-orbits.json"
INPUT = HERE / "specs" / "run-075-input.json"
COLLECT = HERE / "run075_collect.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def group_payload(spec, source, group_id, timeout_orbit=None):
    lookup = {record["orbit_id"]: record for record in source["orbits"]}
    orbit_ids = sorted(
        orbit for assignment in spec["assignments"] if assignment["group"] == group_id
        for orbit in assignment["orbit_ids"]
    )
    records = []
    for orbit_id in orbit_ids:
        status = "TIMEOUT" if orbit_id == timeout_orbit else "UNSAT_DIAGNOSTIC"
        records.append({
            "orbit_id": orbit_id,
            "orbit_size": lookup[orbit_id]["orbit_size"],
            "partition": lookup[orbit_id]["partition"],
            "status": status,
            "solver_exit": 124 if status == "TIMEOUT" else 20,
            "variable_count": 145,
            "clause_count": 1,
            "cnf_sha256": "0" * 64,
            "solver_log_sha256": "1" * 64,
        })
    return {
        "schema": "neutral-bounded-orbit-group-v1",
        "group": group_id,
        "source_sha": "a" * 40,
        "spec_sha256": sha(SPEC),
        "input_sha256": sha(INPUT),
        "records": records,
    }


def run(groups, output):
    return subprocess.run([
        sys.executable, str(COLLECT), "--spec", str(SPEC), "--input", str(INPUT),
        "--groups", str(groups), "--output", str(output),
    ], check=False, capture_output=True, text=True)


def main():
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    source = json.loads(INPUT.read_text(encoding="utf-8"))
    explicit_root = os.environ.get("RUN075_TEST_ROOT")
    if explicit_root:
        root = Path(explicit_root)
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True)
        raw_context = None
    else:
        raw_context = tempfile.TemporaryDirectory(prefix="run075-collector-")
        root = Path(raw_context.__enter__())
    try:
        groups = root / "groups"
        groups.mkdir()
        for group_id in range(19):
            (groups / f"group-{group_id}.json").write_text(
                json.dumps(group_payload(spec, source, group_id), sort_keys=True) + "\n",
                encoding="utf-8",
            )
        accepted = run(groups, root / "accepted.json")
        assert accepted.returncode == 0, accepted.stderr
        payload = json.loads((root / "accepted.json").read_text(encoding="utf-8"))
        assert payload["accepted_technical_coverage"] is True
        assert payload["negative_statuses_promoted_to_theorem"] is False
        assert payload["status_histogram"] == {"UNSAT_DIAGNOSTIC": 178}
        assert [record["orbit_id"] for record in payload["records"]] == list(range(1, 179))

        (groups / "group-18.json").unlink()
        missing = run(groups, root / "missing.json")
        assert missing.returncode != 0
        (groups / "group-18.json").write_text(
            json.dumps(group_payload(spec, source, 18), sort_keys=True) + "\n", encoding="utf-8"
        )
        (groups / "group-0.json").write_text(
            json.dumps(group_payload(spec, source, 0, timeout_orbit=1), sort_keys=True) + "\n", encoding="utf-8"
        )
        timeout = run(groups, root / "timeout.json")
        assert timeout.returncode == 2
        payload = json.loads((root / "timeout.json").read_text(encoding="utf-8"))
        assert payload["accepted_technical_coverage"] is False
        assert payload["status_histogram"]["TIMEOUT"] == 1
    finally:
        if raw_context is not None:
            raw_context.__exit__(None, None, None)
    print("run075 collector tests: accepted")


if __name__ == "__main__":
    main()
