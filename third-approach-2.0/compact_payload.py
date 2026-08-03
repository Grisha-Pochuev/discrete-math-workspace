#!/usr/bin/env python3
"""Stream a large Third approach 2.0 result bundle into a compact collector payload.

The full worker bundle may contain multi-gigabyte metrics.jsonl files.  The
scientific collector needs manifests and saved candidate records, while a
small set of diagnostics is useful for auditing.  This tool reads the tar.gz
sequentially and copies only those files, without expanding the complete tree.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile

DIAGNOSTIC_BASENAMES = {
    "manifest.json",
    "config.json",
    "system.txt",
    "driver.log",
    "resource-monitor.log",
    "runner-exit-code.txt",
    "checkpoint.json",
    "complete.json",
    "errors.jsonl",
    "warnings.jsonl",
}


def normalized_member_name(name: str) -> PurePosixPath:
    clean = name.removeprefix("./")
    path = PurePosixPath(clean)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe archive member: {name!r}")
    return path


def wanted(path: PurePosixPath) -> bool:
    base = path.name
    if base in DIAGNOSTIC_BASENAMES:
        return True
    return base.startswith("candidate-") and base.endswith(".json.gz")


def compact(bundle: Path, output: Path) -> dict[str, int]:
    if not bundle.is_file():
        raise FileNotFoundError(bundle)
    output.mkdir(parents=True, exist_ok=True)

    copied = 0
    candidates = 0
    manifests = 0
    copied_bytes = 0
    skipped_bytes = 0

    with tarfile.open(bundle, mode="r:gz") as archive:
        for member in archive:
            if not member.isfile():
                continue
            path = normalized_member_name(member.name)
            if not wanted(path):
                skipped_bytes += max(0, int(member.size))
                continue
            source = archive.extractfile(member)
            if source is None:
                continue
            destination = output.joinpath(*path.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with source, destination.open("wb") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)
            copied += 1
            copied_bytes += int(member.size)
            if path.name == "manifest.json":
                manifests += 1
            if path.name.startswith("candidate-") and path.name.endswith(".json.gz"):
                candidates += 1

    if manifests != 1:
        raise RuntimeError(f"expected exactly one manifest.json, found {manifests}")
    if candidates < 1:
        raise RuntimeError("compact payload contains no saved candidates")

    summary = {
        "copied_files": copied,
        "candidate_files": candidates,
        "manifest_files": manifests,
        "copied_bytes": copied_bytes,
        "skipped_uncompressed_bytes": skipped_bytes,
    }
    (output / "compaction.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(compact(args.bundle, args.output), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
