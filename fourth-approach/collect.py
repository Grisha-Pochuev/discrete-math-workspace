#!/usr/bin/env python3
"""Aggregate immutable Fourth approach shard artifacts and update control state."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from schema import APPROACH, read_json, validate_spec


def atomic_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def read_gzip_json(path: Path) -> Any:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def discover_artifact_dirs(root: Path) -> list[Path]:
    return sorted({p.parent for p in root.rglob("manifest.json")})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--expected-jobs", type=int, required=True)
    parser.add_argument("--minimum-jobs", type=int, required=True)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--rescue", action="store_true")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    artifacts = Path(args.artifacts).resolve()
    spec = validate_spec(read_json(args.spec))
    run_index = int(spec["run_index"])
    task = str(spec["task"])
    runs_root = repo / "fourth-approach" / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    run_dir = runs_root / f"run-{run_index:03d}-{args.run_id}"
    for prior in sorted(runs_root.glob(f"run-{run_index:03d}-*")):
        summary_path = prior / "summary.json"
        if not summary_path.is_file():
            continue
        existing = read_json(summary_path)
        if int(existing.get("run_id", -1)) == args.run_id:
            print(f"archive already exists: {prior}")
            return 0
        if existing.get("accepted") is True:
            raise SystemExit(
                f"refusing duplicate accepted research index {run_index}; existing archive: {prior}"
            )
    if run_dir.exists():
        raise SystemExit(f"refusing to overwrite immutable archive: {run_dir}")
    run_dir.mkdir(parents=True)

    manifests: list[dict[str, Any]] = []
    records_by_path: dict[str, dict[str, Any]] = {}
    unreadable: list[dict[str, str]] = []
    worker_errors: list[dict[str, Any]] = []
    for directory in discover_artifact_dirs(artifacts):
        manifest = read_json(directory / "manifest.json")
        manifests.append(manifest)
        if manifest.get("status") != "SUCCESS":
            worker_errors.append(manifest)
            continue
        result_file = manifest.get("result_file")
        result_path = directory / str(result_file)
        if not result_file or not result_path.exists():
            worker_errors.append({**manifest, "collector_error": "missing result file"})
            continue
        payload = read_gzip_json(result_path)
        for record in payload.get("records", []):
            path = str(record["path"])
            previous = records_by_path.get(path)
            if previous and previous.get("sha256") != record.get("sha256"):
                worker_errors.append({"collector_error": "conflicting record", "path": path})
            else:
                records_by_path[path] = record
        unreadable.extend(payload.get("unreadable", []))

    completed = sum(1 for m in manifests if m.get("status") == "SUCCESS")
    accepted = (
        completed >= args.minimum_jobs
        and not worker_errors
        and not unreadable
        and len(manifests) <= args.expected_jobs
    )
    records = [records_by_path[k] for k in sorted(records_by_path)]
    hash_counts: dict[str, int] = {}
    for record in records:
        hash_counts[record["sha256"]] = hash_counts.get(record["sha256"], 0) + 1

    required_run = spec.get("source_commit_requirements", {}).get(
        "third_approach_2_0_last_accepted_run_id"
    )
    found_required_run = any(
        record.get("summary", {}).get("run_id") == required_run
        and record.get("summary", {}).get("accepted") is True
        for record in records
    )
    if spec.get("acceptance_criteria", {}).get("require_last_third_2_0_run", False):
        accepted = accepted and found_required_run

    source_manifest = {
        "schema_version": 1,
        "approach": APPROACH,
        "run_id": args.run_id,
        "run_index": run_index,
        "task": task,
        "source_sha": args.source_sha,
        "records": records,
        "unreadable": unreadable,
    }
    atomic_json(run_dir / "source-manifest.json", source_manifest)
    atomic_json(run_dir / "job-manifests.json", {"manifests": manifests, "errors": worker_errors})

    metrics = {
        "files_inventoried": len(records),
        "bytes_inventoried": sum(int(x.get("bytes", 0)) for x in records),
        "accepted_run_summaries": sum(
            1 for x in records if x.get("summary", {}).get("accepted") is True
        ),
        "exact_certificate_archives": sum(
            1
            for x in records
            if x["path"].startswith("third-approach-2.0/")
            and x.get("kind") == "compressed_json_archive"
        ),
        "second_approach_candidate_archives": sum(
            1
            for x in records
            if x["path"].startswith(("second-approach/", "second-approach-2.0/"))
            and x.get("kind") == "compressed_json_archive"
        ),
        "unreadable_files": len(unreadable),
        "duplicate_content_hashes": sum(1 for n in hash_counts.values() if n > 1),
        "required_third_2_0_run_found": found_required_run,
    }
    summary = {
        "schema_version": 1,
        "approach": APPROACH,
        "accepted": accepted,
        "rescue": bool(args.rescue),
        "run_id": args.run_id,
        "run_index": run_index,
        "task": task,
        "source_sha": args.source_sha,
        "expected_jobs": args.expected_jobs,
        "minimum_jobs": args.minimum_jobs,
        "artifact_directories_found": len(manifests),
        "completed_jobs": completed,
        "worker_error_count": len(worker_errors),
        "metrics": metrics,
        "scientific_interpretation": "This run freezes the source frontier; it does not prove or refute the Krenn--Gu conjecture.",
        "next_decision": spec["next_decision"],
    }
    atomic_json(run_dir / "summary.json", summary)

    readme = f"""# Fourth approach run {run_index:03d}\n\n- GitHub Actions run: `{args.run_id}`\n- Task: `{task}`\n- Source commit: `{args.source_sha}`\n- Accepted: `{accepted}` ({completed}/{args.expected_jobs} successful shards)\n- Files inventoried: `{metrics['files_inventoried']}`\n- Accepted run summaries: `{metrics['accepted_run_summaries']}`\n- Third approach 2.0 exact archives: `{metrics['exact_certificate_archives']}`\n- Second approach candidate archives: `{metrics['second_approach_candidate_archives']}`\n- Required Third approach 2.0 run found: `{found_required_run}`\n\nThis archive is an immutable research-source inventory for later canonicalization and GPT-5.6 Sol handoff preparation. It is not a proof of the full conjecture.\n"""
    (run_dir / "README.md").write_text(readme, encoding="utf-8")

    checksum_lines = []
    for path in sorted(run_dir.iterdir()):
        if path.is_file() and path.name != "checksums.sha256":
            checksum_lines.append(f"{sha256(path)}  {path.name}")
    (run_dir / "checksums.sha256").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    control_path = repo / "fourth-approach" / "control.json"
    control = read_json(control_path)
    if accepted:
        history = list(control.get("run_history", []))
        history.append(
            {
                "run_id": args.run_id,
                "run_index": run_index,
                "task": task,
                "accepted": True,
                "source_sha": args.source_sha,
                "metrics": metrics,
            }
        )
        control.update(
            completed_runs=int(control.get("completed_runs", 0)) + 1,
            last_run_id=args.run_id,
            last_run_index=run_index,
            last_run_accepted=True,
            next_run_index=run_index + 1,
            current_stage=1,
            current_stage_name="canonicalization_and_independent_verification",
            next_task="stage1_canonicalize_verify",
            next_spec_path="fourth-approach/run-specs/run-001-stage1-canonicalize-verify.json",
            smoke_required=True,
            recommended_next_action="review_run_000_then_implement_and_smoke_run_001",
            run_history=history,
        )
    else:
        control.update(
            last_run_id=args.run_id,
            last_run_index=run_index,
            last_run_accepted=False,
            recommended_next_action="inspect_failure_and_rescue_or_fix_without_advancing_stage",
        )
    atomic_json(control_path, control)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if accepted else 3


if __name__ == "__main__":
    raise SystemExit(main())
