#!/usr/bin/env python3
"""Deterministic source inventory for Fourth approach run 000."""
from __future__ import annotations

import fnmatch
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

SUMMARY_KEYS = {
    "accepted",
    "approach",
    "attempts",
    "best_certificate_score",
    "candidate_count",
    "completed_jobs",
    "distinct_basins",
    "distinct_lineages",
    "distinct_supports",
    "exact_verified_count",
    "expected_jobs",
    "global_best_certificate_score",
    "median_saved_score",
    "run_id",
    "run_index",
    "strategy_profile",
    "worker_errors",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def matches_any(path: str, patterns: Iterable[str]) -> bool:
    for pattern in patterns:
        candidates = {pattern}
        if "/**/*" in pattern:
            candidates.add(pattern.replace("/**/*", "/**"))
        if any(fnmatch.fnmatch(path, candidate) for candidate in candidates):
            return True
    return False


def classify(path: str) -> str:
    if path.endswith("/summary.json"):
        return "run_summary"
    if path.endswith(".json.gz") or path.endswith(".jsonl.gz"):
        return "compressed_json_archive"
    if path.endswith(".md"):
        return "documentation"
    if path.endswith(".json"):
        return "json"
    if path.endswith(".py"):
        return "python"
    if path.endswith((".yml", ".yaml")):
        return "workflow_or_yaml"
    return "other"


def parse_summary(path: Path) -> dict[str, Any] | None:
    if path.name != "summary.json":
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    return {key: raw.get(key) for key in sorted(SUMMARY_KEYS) if key in raw}


def inventory_shard(repo: Path, spec: dict[str, Any], shard_id: int, shard_count: int) -> dict[str, Any]:
    include = [str(x) for x in spec.get("include_globs", [])]
    exclude = [str(x) for x in spec.get("exclude_globs", [])]
    records: list[dict[str, Any]] = []
    unreadable: list[dict[str, str]] = []

    for path in sorted(repo.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(repo).as_posix()
        if include and not matches_any(rel, include):
            continue
        if exclude and matches_any(rel, exclude):
            continue
        bucket = int(hashlib.sha256(rel.encode("utf-8")).hexdigest()[:16], 16) % shard_count
        if bucket != shard_id:
            continue
        try:
            size = path.stat().st_size
            digest = sha256_file(path)
            record: dict[str, Any] = {
                "path": rel,
                "bytes": size,
                "sha256": digest,
                "kind": classify(rel),
            }
            summary = parse_summary(path) if spec.get("parse_summary_json", True) else None
            if summary is not None:
                record["summary"] = summary
            records.append(record)
        except OSError as exc:
            unreadable.append({"path": rel, "error": str(exc)})

    hashes: dict[str, int] = {}
    for record in records:
        hashes[record["sha256"]] = hashes.get(record["sha256"], 0) + 1

    return {
        "schema_version": 1,
        "task": "stage0_source_inventory",
        "shard_id": shard_id,
        "shard_count": shard_count,
        "records": records,
        "unreadable": unreadable,
        "metrics": {
            "files_inventoried": len(records),
            "bytes_inventoried": sum(int(x["bytes"]) for x in records),
            "accepted_run_summaries": sum(
                1 for x in records if x.get("summary", {}).get("accepted") is True
            ),
            "exact_certificate_archives": sum(
                1
                for x in records
                if x["path"].startswith("third-approach-2.0/")
                and x["kind"] == "compressed_json_archive"
            ),
            "second_approach_candidate_archives": sum(
                1
                for x in records
                if x["path"].startswith(("second-approach/", "second-approach-2.0/"))
                and x["kind"] == "compressed_json_archive"
            ),
            "unreadable_files": len(unreadable),
            "duplicate_content_hashes_within_shard": sum(1 for n in hashes.values() if n > 1),
        },
    }


def write_gzip_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=6) as handle:
        json.dump(data, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
