#!/usr/bin/env python3
"""Independent structural verifier for Fourth approach run archives."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from schema import APPROACH, read_json


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument("--require-accepted", action="store_true")
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    required = [
        "README.md",
        "summary.json",
        "source-manifest.json",
        "job-manifests.json",
        "checksums.sha256",
    ]
    for name in required:
        if not (run_dir / name).is_file():
            raise SystemExit(f"missing archive file: {name}")
    summary = read_json(run_dir / "summary.json")
    manifest = read_json(run_dir / "source-manifest.json")
    jobs = read_json(run_dir / "job-manifests.json")
    if summary.get("approach") != APPROACH or manifest.get("approach") != APPROACH:
        raise SystemExit("approach mismatch")
    if args.require_accepted and summary.get("accepted") is not True:
        raise SystemExit("run is not accepted")
    if int(summary.get("completed_jobs", -1)) != sum(
        1 for m in jobs.get("manifests", []) if m.get("status") == "SUCCESS"
    ):
        raise SystemExit("completed job count mismatch")
    paths = [record.get("path") for record in manifest.get("records", [])]
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise SystemExit("source manifest paths are not sorted and unique")
    expected = {}
    for line in (run_dir / "checksums.sha256").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        expected[name] = digest
    for name, digest in expected.items():
        if sha256(run_dir / name) != digest:
            raise SystemExit(f"checksum mismatch: {name}")
    print(json.dumps({"verified": True, "run_dir": str(run_dir), "summary": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
