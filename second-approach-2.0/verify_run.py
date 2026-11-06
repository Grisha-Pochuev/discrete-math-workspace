#!/usr/bin/env python3
"""Verify an archived Second approach 2.0 run without recomputing it."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    root = args.run_dir.resolve()
    summary_path = root / "summary.json"
    manifests_path = root / "job-manifests.json"
    checksums_path = root / "checksums.sha256"
    if not summary_path.exists() or not manifests_path.exists() or not checksums_path.exists():
        raise SystemExit("missing required archive files")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    manifests = json.loads(manifests_path.read_text(encoding="utf-8"))["manifests"]
    assert summary["approach"] == "second-approach-2.0-independent-basin-counterexample-search"
    assert summary["accepted"]
    assert len({int(item["job_id"]) for item in manifests}) >= int(summary["minimum_jobs_for_acceptance"])
    assert int(summary["promoted_candidates"]) > 0
    assert float(summary["best_max_error"]) >= 0.0
    assert int(summary["distinct_support_fingerprints"]) > 0
    assert int(summary["distinct_residual_basin_fingerprints"]) > 0

    for line in checksums_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split("  ", 1)
        path = root / relative
        assert path.is_file(), relative
        assert sha256(path) == expected, relative

    promoted = list((root / "promoted").glob("*.json.gz"))
    assert len(promoted) == int(summary["promoted_candidates"])
    print(json.dumps({
        "verified": True,
        "run_id": summary["run_id"],
        "run_index": summary["run_index"],
        "best_max_error": summary["best_max_error"],
        "best_independent_max_error": summary["best_independent_max_error"],
        "promoted_candidates": len(promoted),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
