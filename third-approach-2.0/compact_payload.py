#!/usr/bin/env python3
"""Stream a large Third approach 2.0 result bundle into a bounded payload.

Old runs may contain hundreds of thousands of orphaned exact-candidate files in
addition to multi-gigabyte metrics logs.  The collector needs a representative,
auditable subset: the strongest candidates, exact restricted certificates, and
champions from different basins and lineages.  This tool reads the source tar.gz
sequentially and keeps those bounded sets in memory without expanding the full
tree.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
from pathlib import Path, PurePosixPath
import shutil
import tarfile
from typing import Any

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

GLOBAL_LIMIT = 480
EXACT_LIMIT = 240
BASIN_LIMIT = 240
LINEAGE_LIMIT = 240


def normalized_member_name(name: str) -> PurePosixPath:
    clean = name.removeprefix("./")
    path = PurePosixPath(clean)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe archive member: {name!r}")
    return path


def is_candidate(path: PurePosixPath) -> bool:
    return path.name.startswith("candidate-") and path.name.endswith(".json.gz")


def prune_unkeyed(store: dict[str, dict[str, Any]], limit: int) -> None:
    if len(store) <= limit:
        return
    ranked = sorted(store.values(), key=lambda item: (item["score"], item["candidate_id"]))[:limit]
    store.clear()
    store.update((item["candidate_id"], item) for item in ranked)


def consider_unkeyed(
    store: dict[str, dict[str, Any]], record: dict[str, Any], limit: int
) -> None:
    candidate_id = record["candidate_id"]
    previous = store.get(candidate_id)
    if previous is None or record["score"] < previous["score"]:
        store[candidate_id] = record
    if len(store) > 2 * limit:
        prune_unkeyed(store, limit)


def prune_keyed(store: dict[str, dict[str, Any]], limit: int) -> None:
    if len(store) <= limit:
        return
    ranked = sorted(store.values(), key=lambda item: (item["score"], item["candidate_id"]))[:limit]
    store.clear()
    for item in ranked:
        store[item["selection_key"]] = item


def consider_keyed(
    store: dict[str, dict[str, Any]],
    key: str,
    record: dict[str, Any],
    limit: int,
) -> None:
    selected = dict(record)
    selected["selection_key"] = key
    previous = store.get(key)
    if previous is None or selected["score"] < previous["score"]:
        store[key] = selected
    if len(store) > 2 * limit:
        prune_keyed(store, limit)


def copy_stream(source: Any, destination: Path) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as target:
        shutil.copyfileobj(source, target, length=1024 * 1024)
    return destination.stat().st_size


def parse_candidate(path: PurePosixPath, payload: bytes) -> dict[str, Any] | None:
    try:
        document = json.loads(gzip.decompress(payload).decode("utf-8"))
        score = float(document["certificate_score"])
        candidate_id = str(document.get("candidate_id") or path.name)
    except Exception:
        return None
    if not math.isfinite(score) or not candidate_id:
        return None
    return {
        "candidate_id": candidate_id,
        "score": score,
        "path": path,
        "payload": payload,
        "exact_verified": bool(document.get("exact_verified", False)),
        "basin": str(document.get("basin_fingerprint", "unknown")),
        "lineage": str(document.get("lineage_root", candidate_id)),
    }


def compact(bundle: Path, output: Path) -> dict[str, int]:
    if not bundle.is_file():
        raise FileNotFoundError(bundle)
    output.mkdir(parents=True, exist_ok=True)

    copied_files = 0
    copied_bytes = 0
    skipped_bytes = 0
    manifests = 0
    seen_candidates = 0
    seen_exact = 0
    malformed_candidates = 0
    candidate_bytes_seen = 0

    strongest: dict[str, dict[str, Any]] = {}
    exact: dict[str, dict[str, Any]] = {}
    basins: dict[str, dict[str, Any]] = {}
    lineages: dict[str, dict[str, Any]] = {}

    with tarfile.open(bundle, mode="r:gz") as archive:
        for member in archive:
            if not member.isfile():
                continue
            path = normalized_member_name(member.name)
            if path.name in DIAGNOSTIC_BASENAMES:
                source = archive.extractfile(member)
                if source is None:
                    continue
                with source:
                    copied_bytes += copy_stream(source, output.joinpath(*path.parts))
                copied_files += 1
                if path.name == "manifest.json":
                    manifests += 1
                continue
            if not is_candidate(path):
                skipped_bytes += max(0, int(member.size))
                continue

            source = archive.extractfile(member)
            if source is None:
                continue
            with source:
                payload = source.read()
            seen_candidates += 1
            candidate_bytes_seen += len(payload)
            record = parse_candidate(path, payload)
            if record is None:
                malformed_candidates += 1
                continue
            consider_unkeyed(strongest, record, GLOBAL_LIMIT)
            if record["exact_verified"]:
                seen_exact += 1
                consider_unkeyed(exact, record, EXACT_LIMIT)
            consider_keyed(basins, record["basin"], record, BASIN_LIMIT)
            consider_keyed(lineages, record["lineage"], record, LINEAGE_LIMIT)

    if manifests != 1:
        raise RuntimeError(f"expected exactly one manifest.json, found {manifests}")
    if seen_candidates < 1:
        raise RuntimeError("source bundle contains no saved candidates")

    prune_unkeyed(strongest, GLOBAL_LIMIT)
    prune_unkeyed(exact, EXACT_LIMIT)
    prune_keyed(basins, BASIN_LIMIT)
    prune_keyed(lineages, LINEAGE_LIMIT)

    retained: dict[str, dict[str, Any]] = {}
    for group in (strongest.values(), exact.values(), basins.values(), lineages.values()):
        for item in group:
            current = retained.get(item["candidate_id"])
            if current is None or item["score"] < current["score"]:
                retained[item["candidate_id"]] = item

    retained_candidate_bytes = 0
    for item in sorted(retained.values(), key=lambda value: (value["score"], value["candidate_id"])):
        destination = output.joinpath(*item["path"].parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(item["payload"])
        size = len(item["payload"])
        retained_candidate_bytes += size
        copied_bytes += size
        copied_files += 1

    skipped_bytes += max(0, candidate_bytes_seen - retained_candidate_bytes)
    summary = {
        "copied_files": copied_files,
        "candidate_files": len(retained),
        "seen_candidate_files": seen_candidates,
        "seen_exact_candidates": seen_exact,
        "malformed_candidate_files": malformed_candidates,
        "manifest_files": manifests,
        "copied_bytes": copied_bytes,
        "skipped_uncompressed_bytes": skipped_bytes,
        "global_limit": GLOBAL_LIMIT,
        "exact_limit": EXACT_LIMIT,
        "basin_limit": BASIN_LIMIT,
        "lineage_limit": LINEAGE_LIMIT,
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
