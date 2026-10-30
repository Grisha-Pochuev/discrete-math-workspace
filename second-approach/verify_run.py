#!/usr/bin/env python3
"""Verify a committed second-approach run archive."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    args = ap.parse_args()
    root = args.run_dir.resolve()
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    checksums = {}
    for line in (root / "checksums.sha256").read_text(encoding="utf-8").splitlines():
        expected, name = line.split(maxsplit=1)
        checksums[name] = expected
    actual_files = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "checksums.sha256"
    )
    assert actual_files == sorted(checksums), (actual_files, sorted(checksums))
    for name, expected in checksums.items():
        assert digest(root / name) == expected, name

    attempts = 0
    parts = sorted((root / "attempts").glob("part-*.jsonl.gz"))
    assert parts
    for part in parts:
        with gzip.open(part, "rt", encoding="utf-8") as source:
            for line in source:
                if line.strip():
                    json.loads(line)
                    attempts += 1
    assert attempts == int(summary["attempts_total"])

    promoted = list((root / "promoted").glob("*.json.gz"))
    for path in promoted:
        with gzip.open(path, "rt", encoding="utf-8") as source:
            payload = json.load(source)
        assert "candidate_id" in payload
        assert len(payload.get("active_variables", [])) == len(
            payload.get("active_weights", [])
        )

    print(json.dumps({
        "verified": True,
        "run_dir": str(root),
        "attempts": attempts,
        "promoted_candidates": len(promoted),
        "jobs_present": len(summary["jobs_present"]),
        "accepted": bool(summary.get("accepted", False)),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
