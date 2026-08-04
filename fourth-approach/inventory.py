#!/usr/bin/env python3
"""Deterministic Git-tree source inventory for Fourth approach run 000."""
from __future__ import annotations

import fnmatch
import gzip
import hashlib
import json
import subprocess
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


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def git_tree_entries(repo: Path, ref: str = "HEAD") -> list[dict[str, Any]]:
    result = _git(repo, "ls-tree", "-r", "-l", "-z", ref)
    entries: list[dict[str, Any]] = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        metadata, raw_path = raw.split(b"\t", 1)
        mode, object_type, oid, raw_size = metadata.decode("ascii").split()
        if object_type != "blob":
            continue
        entries.append(
            {
                "path": raw_path.decode("utf-8", errors="surrogateescape"),
                "mode": mode,
                "git_blob_oid": oid,
                "bytes": int(raw_size),
            }
        )
    return entries


def git_read_blob(repo: Path, ref: str, path: str) -> bytes:
    return _git(repo, "show", f"{ref}:{path}").stdout


def parse_summary_bytes(raw: bytes) -> dict[str, Any] | None:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict):
        return None
    return {key: value.get(key) for key in sorted(SUMMARY_KEYS) if key in value}


def should_parse_summary(spec: dict[str, Any], path: str) -> bool:
    if not path.endswith("/summary.json"):
        return False
    policy = str(spec.get("parse_summary_policy", "all"))
    if policy == "none":
        return False
    if policy == "required_latest_only":
        required_run = spec.get("source_commit_requirements", {}).get(
            "third_approach_2_0_last_accepted_run_id"
        )
        return required_run is not None and f"-{required_run}/summary.json" in path
    return bool(spec.get("parse_summary_json", True))


def inventory_git_tree_shard(
    repo: Path,
    spec: dict[str, Any],
    shard_id: int,
    shard_count: int,
    *,
    ref: str = "HEAD",
) -> dict[str, Any]:
    include = [str(x) for x in spec.get("include_globs", [])]
    exclude = [str(x) for x in spec.get("exclude_globs", [])]
    records: list[dict[str, Any]] = []
    unreadable: list[dict[str, str]] = []

    for entry in git_tree_entries(repo, ref):
        rel = str(entry["path"])
        if include and not matches_any(rel, include):
            continue
        if exclude and matches_any(rel, exclude):
            continue
        bucket = int(hashlib.sha256(rel.encode("utf-8")).hexdigest()[:16], 16) % shard_count
        if bucket != shard_id:
            continue
        oid = str(entry["git_blob_oid"])
        record: dict[str, Any] = {
            "path": rel,
            "bytes": int(entry["bytes"]),
            "git_blob_oid": oid,
            "content_id": f"git-blob:{oid}",
            "kind": classify(rel),
        }
        if should_parse_summary(spec, rel):
            try:
                summary = parse_summary_bytes(git_read_blob(repo, ref, rel))
                if summary is None:
                    unreadable.append({"path": rel, "error": "invalid summary JSON"})
                else:
                    record["summary"] = summary
            except subprocess.CalledProcessError as exc:
                unreadable.append(
                    {
                        "path": rel,
                        "error": exc.stderr.decode("utf-8", errors="replace")[-2000:],
                    }
                )
        records.append(record)

    content_counts: dict[str, int] = {}
    for record in records:
        key = str(record["content_id"])
        content_counts[key] = content_counts.get(key, 0) + 1

    return {
        "schema_version": 1,
        "task": "stage0_source_inventory",
        "source_ref": ref,
        "identity_scheme": "immutable_commit_path_and_git_blob_oid",
        "shard_id": shard_id,
        "shard_count": shard_count,
        "records": records,
        "unreadable": unreadable,
        "metrics": {
            "files_inventoried": len(records),
            "bytes_referenced": sum(int(x["bytes"]) for x in records),
            "summary_files_inventoried": sum(
                1 for x in records if x["kind"] == "run_summary"
            ),
            "parsed_run_summaries": sum(1 for x in records if "summary" in x),
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
            "duplicate_content_ids_within_shard": sum(
                1 for count in content_counts.values() if count > 1
            ),
        },
    }


def write_gzip_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=6) as handle:
        json.dump(data, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
