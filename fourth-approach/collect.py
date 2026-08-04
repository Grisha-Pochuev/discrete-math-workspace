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

from schema import APPROACH, launch_from_spec, read_json, validate_spec


def atomic_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def write_gzip_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=9) as handle:
        json.dump(data, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
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
    return sorted({path.parent for path in root.rglob("manifest.json")})


def prepare_run_dir(repo: Path, run_index: int, run_id: int) -> Path:
    runs_root = repo / "fourth-approach" / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    run_dir = runs_root / f"run-{run_index:03d}-{run_id}"
    for prior in sorted(runs_root.glob(f"run-{run_index:03d}-*")):
        summary_path = prior / "summary.json"
        if not summary_path.is_file():
            continue
        existing = read_json(summary_path)
        if int(existing.get("run_id", -1)) == run_id:
            print(f"archive already exists: {prior}")
            return prior
        if existing.get("accepted") is True:
            raise SystemExit(
                f"refusing duplicate accepted research index {run_index}; existing archive: {prior}"
            )
    if run_dir.exists():
        raise SystemExit(f"refusing to overwrite immutable archive: {run_dir}")
    run_dir.mkdir(parents=True)
    return run_dir


def load_artifacts(artifacts: Path) -> tuple[list[dict[str, Any]], list[tuple[dict[str, Any], dict[str, Any]]], list[dict[str, Any]]]:
    manifests: list[dict[str, Any]] = []
    payloads: list[tuple[dict[str, Any], dict[str, Any]]] = []
    technical_errors: list[dict[str, Any]] = []
    for directory in discover_artifact_dirs(artifacts):
        try:
            manifest = read_json(directory / "manifest.json")
        except Exception as exc:
            technical_errors.append({"directory": str(directory), "error": f"manifest: {exc}"})
            continue
        manifests.append(manifest)
        if manifest.get("status") not in {"SUCCESS", "BOUNDED_INCOMPLETE"}:
            technical_errors.append(manifest)
            continue
        result_file = manifest.get("result_file")
        result_path = directory / str(result_file)
        if not result_file or not result_path.exists():
            technical_errors.append({**manifest, "collector_error": "missing result file"})
            continue
        try:
            payload = read_gzip_json(result_path)
        except Exception as exc:
            technical_errors.append({**manifest, "collector_error": f"unreadable result: {exc}"})
            continue
        payloads.append((manifest, payload))
    return manifests, payloads, technical_errors


def record_content_id(record: dict[str, Any]) -> str:
    value = record.get("content_id") or record.get("sha256")
    if not value:
        raise ValueError(f"record has no content identity: {record.get('path')}")
    return str(value)


def collect_stage0(
    run_dir: Path,
    spec: dict[str, Any],
    manifests: list[dict[str, Any]],
    payloads: list[tuple[dict[str, Any], dict[str, Any]]],
    technical_errors: list[dict[str, Any]],
    *,
    run_id: int,
    source_sha: str,
    expected_jobs: int,
    minimum_jobs: int,
    rescue: bool,
    smoke: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    records_by_path: dict[str, dict[str, Any]] = {}
    unreadable: list[dict[str, str]] = []
    worker_errors = list(technical_errors)
    for _manifest, payload in payloads:
        for record in payload.get("records", []):
            path = str(record["path"])
            previous = records_by_path.get(path)
            if previous and record_content_id(previous) != record_content_id(record):
                worker_errors.append({"collector_error": "conflicting record", "path": path})
            else:
                records_by_path[path] = record
        unreadable.extend(payload.get("unreadable", []))

    completed = sum(1 for manifest in manifests if manifest.get("status") == "SUCCESS")
    accepted = (
        completed >= minimum_jobs
        and not worker_errors
        and not unreadable
        and len(manifests) <= expected_jobs
    )
    records = [records_by_path[key] for key in sorted(records_by_path)]
    content_counts: dict[str, int] = {}
    for record in records:
        identity = record_content_id(record)
        content_counts[identity] = content_counts.get(identity, 0) + 1

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
        "identity_scheme": "immutable_commit_path_and_git_blob_oid",
        "run_id": run_id,
        "run_index": int(spec["run_index"]),
        "task": spec["task"],
        "source_sha": source_sha,
        "records": records,
        "unreadable": unreadable,
    }
    atomic_json(run_dir / "source-manifest.json", source_manifest)
    atomic_json(run_dir / "job-manifests.json", {"manifests": manifests, "errors": worker_errors})
    metrics = {
        "files_inventoried": len(records),
        "bytes_referenced": sum(int(record.get("bytes", 0)) for record in records),
        "summary_files_inventoried": sum(1 for record in records if record.get("kind") == "run_summary"),
        "parsed_run_summaries": sum(1 for record in records if "summary" in record),
        "accepted_run_summaries": sum(1 for record in records if record.get("summary", {}).get("accepted") is True),
        "exact_certificate_archives": sum(
            1 for record in records
            if record["path"].startswith("third-approach-2.0/")
            and record.get("kind") == "compressed_json_archive"
        ),
        "second_approach_candidate_archives": sum(
            1 for record in records
            if record["path"].startswith(("second-approach/", "second-approach-2.0/"))
            and record.get("kind") == "compressed_json_archive"
        ),
        "unreadable_files": len(unreadable),
        "duplicate_content_ids": sum(1 for count in content_counts.values() if count > 1),
        "required_third_2_0_run_found": found_required_run,
    }
    summary = {
        "schema_version": 1,
        "approach": APPROACH,
        "accepted": accepted,
        "smoke": smoke,
        "rescue": rescue,
        "run_id": run_id,
        "run_index": int(spec["run_index"]),
        "task": spec["task"],
        "source_sha": source_sha,
        "expected_jobs": expected_jobs,
        "minimum_jobs": minimum_jobs,
        "artifact_directories_found": len(manifests),
        "completed_jobs": completed,
        "worker_error_count": len(worker_errors),
        "metrics": metrics,
        "scientific_interpretation": "This run freezes the source frontier; it does not prove or refute the Krenn--Gu conjecture.",
        "next_decision": spec["next_decision"],
    }
    return summary, metrics


def collect_stage1(
    run_dir: Path,
    spec: dict[str, Any],
    manifests: list[dict[str, Any]],
    payloads: list[tuple[dict[str, Any], dict[str, Any]]],
    technical_errors: list[dict[str, Any]],
    *,
    run_id: int,
    source_sha: str,
    expected_jobs: int,
    minimum_jobs: int,
    rescue: bool,
    smoke: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    worker_errors = list(technical_errors)
    records_by_key: dict[str, dict[str, Any]] = {}
    global_exact_counts: set[int] = set()
    global_raw_counts: set[int] = set()
    complete_flags: list[bool] = []
    for manifest, payload in payloads:
        if payload.get("task") != "stage1_canonicalize_verify":
            worker_errors.append({**manifest, "collector_error": "wrong payload task"})
            continue
        complete_flags.append(bool(payload.get("complete", False)))
        metrics = payload.get("metrics", {})
        global_exact_counts.add(int(metrics.get("global_claimed_exact", -1)))
        global_raw_counts.add(int(metrics.get("global_raw_candidates", -1)))
        for record in payload.get("records", []):
            key = str(record.get("candidate_key", ""))
            if not key:
                worker_errors.append({"collector_error": "candidate record has no key"})
                continue
            previous = records_by_key.get(key)
            if previous is not None and previous != record:
                worker_errors.append({"collector_error": "conflicting candidate record", "candidate_key": key})
            else:
                records_by_key[key] = record

    completed = sum(
        1 for manifest in manifests
        if manifest.get("status") == "SUCCESS" or (smoke and manifest.get("status") == "BOUNDED_INCOMPLETE")
    )
    records = [records_by_key[key] for key in sorted(records_by_key)]
    production_claims = [record for record in records if record.get("production_exact_verified") is True]
    verified = [record for record in production_claims if record.get("independent_exact_verified") is True]
    rejected = [record for record in production_claims if record.get("independent_exact_verified") is not True]
    non_exact = [record for record in records if record.get("production_exact_verified") is not True]
    expected_exact = next(iter(global_exact_counts)) if len(global_exact_counts) == 1 else -1
    expected_raw = next(iter(global_raw_counts)) if len(global_raw_counts) == 1 else -1
    coverage_ok = smoke or (expected_exact >= 0 and len(production_claims) == expected_exact)
    complete_ok = smoke or (len(complete_flags) == expected_jobs and all(complete_flags))
    accepted = (
        completed >= minimum_jobs
        and not worker_errors
        and not rejected
        and coverage_ok
        and complete_ok
        and bool(verified)
        and len(manifests) <= expected_jobs
    )

    classes: dict[str, dict[str, Any]] = {}
    for record in verified:
        support_id = str(record["canonical_support_id"])
        entry = classes.setdefault(
            support_id,
            {
                "canonical_support_id": support_id,
                "canonical_support_variables": record["canonical_support_variables"],
                "member_count": 0,
                "certificate_signatures": set(),
                "source_run_ids": set(),
                "representative": None,
            },
        )
        entry["member_count"] += 1
        entry["certificate_signatures"].add(str(record["canonical_certificate_signature"]))
        if record.get("source_run_id") is not None:
            entry["source_run_ids"].add(int(record["source_run_id"]))
        representative = {
            key: record.get(key)
            for key in (
                "candidate_id",
                "candidate_key",
                "source_path",
                "source_run_id",
                "support_size",
                "max_multiplier_degree",
                "descriptor_count",
                "nonzero_coefficients",
                "certificate_score",
                "canonical_certificate_signature",
            )
        }
        current = entry["representative"]
        rank = (
            int(representative.get("nonzero_coefficients") or 10**9),
            int(representative.get("descriptor_count") or 10**9),
            int(representative.get("max_multiplier_degree") or 10**9),
            float(representative.get("certificate_score") or float("inf")),
            str(representative.get("candidate_id")),
        )
        if current is None:
            entry["representative"] = representative
            entry["representative_rank"] = rank
        elif rank < tuple(entry["representative_rank"]):
            entry["representative"] = representative
            entry["representative_rank"] = rank

    canonical_classes = []
    for support_id in sorted(classes):
        entry = classes[support_id]
        canonical_classes.append(
            {
                "canonical_support_id": support_id,
                "canonical_support_variables": entry["canonical_support_variables"],
                "member_count": entry["member_count"],
                "certificate_signature_count": len(entry["certificate_signatures"]),
                "certificate_signatures": sorted(entry["certificate_signatures"]),
                "source_run_ids": sorted(entry["source_run_ids"]),
                "representative": entry["representative"],
            }
        )

    write_gzip_json(
        run_dir / "verification-results.json.gz",
        {
            "schema_version": 1,
            "task": spec["task"],
            "records": records,
        },
    )
    atomic_json(
        run_dir / "canonical-classes.json",
        {
            "schema_version": 1,
            "symmetry_group": "S6_vertex_permutations_times_global_S3_color_permutations",
            "classes": canonical_classes,
        },
    )
    atomic_json(run_dir / "job-manifests.json", {"manifests": manifests, "errors": worker_errors})

    metrics = {
        "raw_candidates_in_source_archives": expected_raw,
        "raw_exact_certificates": expected_exact,
        "processed_candidate_records": len(records),
        "production_exact_claims": len(production_claims),
        "independently_verified_certificates": len(verified),
        "rejected_certificates": len(rejected),
        "non_exact_candidates_encountered": len(non_exact),
        "canonical_support_classes": len(canonical_classes),
        "canonical_certificate_signatures": len({record["canonical_certificate_signature"] for record in verified}),
        "duplicate_exact_certificates_removed": len(verified) - len(canonical_classes),
        "complete_shards": sum(1 for value in complete_flags if value),
        "coverage_ok": coverage_ok,
        "all_full_shards_complete": complete_ok,
    }
    summary = {
        "schema_version": 1,
        "approach": APPROACH,
        "accepted": accepted,
        "smoke": smoke,
        "rescue": rescue,
        "run_id": run_id,
        "run_index": int(spec["run_index"]),
        "task": spec["task"],
        "source_sha": source_sha,
        "expected_jobs": expected_jobs,
        "minimum_jobs": minimum_jobs,
        "artifact_directories_found": len(manifests),
        "completed_jobs": completed,
        "worker_error_count": len(worker_errors),
        "metrics": metrics,
        "scientific_interpretation": (
            "Exact verification and canonical counts apply only to the recorded support-restricted "
            "n=6,d=3 certificate systems. They do not prove the full Krenn--Gu conjecture."
        ),
        "next_decision": spec["next_decision"],
    }
    return summary, metrics


def write_readme(run_dir: Path, summary: dict[str, Any]) -> None:
    metrics = summary["metrics"]
    if summary["task"] == "stage0_source_inventory":
        body = f"""# Fourth approach run {summary['run_index']:03d}\n\n- GitHub Actions run: `{summary['run_id']}`\n- Task: `{summary['task']}`\n- Source commit: `{summary['source_sha']}`\n- Accepted: `{summary['accepted']}` ({summary['completed_jobs']}/{summary['expected_jobs']} successful shards)\n- Files inventoried: `{metrics['files_inventoried']}`\n- Third approach 2.0 exact archives: `{metrics['exact_certificate_archives']}`\n- Second approach candidate archives: `{metrics['second_approach_candidate_archives']}`\n\nThis archive is an immutable research-source inventory. It is not a proof of the full conjecture.\n"""
    else:
        body = f"""# Fourth approach run {summary['run_index']:03d}\n\n- GitHub Actions run: `{summary['run_id']}`\n- Task: `{summary['task']}`\n- Source commit: `{summary['source_sha']}`\n- Accepted: `{summary['accepted']}` ({summary['completed_jobs']}/{summary['expected_jobs']} shards)\n- Raw exact certificates: `{metrics['raw_exact_certificates']}`\n- Independently verified: `{metrics['independently_verified_certificates']}`\n- Canonical support classes: `{metrics['canonical_support_classes']}`\n- Canonical certificate signatures: `{metrics['canonical_certificate_signatures']}`\n- Rejected exact claims: `{metrics['rejected_certificates']}`\n\nThe exact claims concern only recorded support-restricted n=6,d=3 systems. This archive is evidence for GPT-5.6 Sol, not a proof of the full conjecture.\n"""
    (run_dir / "README.md").write_text(body, encoding="utf-8")


def update_state_after_accepted_run(
    repo: Path,
    spec: dict[str, Any],
    summary: dict[str, Any],
    metrics: dict[str, Any],
) -> None:
    control_path = repo / "fourth-approach" / "control.json"
    launch_path = repo / "fourth-approach" / "launch.json"
    state_path = repo / "fourth-approach" / "watchdog-state.json"
    control = read_json(control_path)
    history = list(control.get("run_history", []))
    history.append(
        {
            "run_id": summary["run_id"],
            "run_index": summary["run_index"],
            "task": summary["task"],
            "accepted": True,
            "source_sha": summary["source_sha"],
            "metrics": metrics,
        }
    )
    next_spec_path = str(spec.get("next_spec_path", ""))
    if not next_spec_path:
        raise ValueError("accepted run spec must declare next_spec_path")
    next_spec = validate_spec(read_json(repo / next_spec_path))
    control.update(
        completed_runs=int(control.get("completed_runs", 0)) + 1,
        last_run_id=summary["run_id"],
        last_run_index=summary["run_index"],
        last_run_accepted=True,
        next_run_index=int(next_spec["run_index"]),
        current_stage=int(next_spec["run_index"]),
        current_stage_name=str(next_spec.get("stage_name", next_spec["task"])),
        next_task=str(next_spec["task"]),
        next_spec_path=next_spec_path,
        smoke_required=True,
        smoke_verified_for_code_sha=None,
        recommended_next_action=(
            "implement_next_stage_then_smoke"
            if next_spec.get("implementation_status") != "ready"
            else "smoke_next_stage_then_launch_once"
        ),
        run_history=history,
    )
    next_launch = launch_from_spec(
        next_spec_path,
        next_spec,
        enabled=False,
        nonce=f"fourth-run-{int(next_spec['run_index']):03d}-disabled-after-{summary['run_id']}",
    )
    state = read_json(state_path) if state_path.exists() else {"schema_version": 1}
    state.update(
        last_checked_at=None,
        last_action="accepted_run_and_prepared_next_disabled",
        last_action_commit=summary["source_sha"],
        current_gate=(
            "await_next_stage_implementation"
            if next_spec.get("implementation_status") != "ready"
            else "await_smoke_for_next_stage"
        ),
        last_observed_active_runs=[],
        consecutive_technical_failures=0,
    )
    for key in ("dispatch_requested_at", "dispatch_requested_for_nonce"):
        state.pop(key, None)
    atomic_json(control_path, control)
    atomic_json(launch_path, next_launch)
    atomic_json(state_path, state)


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
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    artifacts = Path(args.artifacts).resolve()
    spec = validate_spec(read_json(args.spec), require_ready=True)
    run_index = int(spec["run_index"])
    run_dir = prepare_run_dir(repo, run_index, args.run_id)
    if (run_dir / "summary.json").exists():
        return 0
    manifests, payloads, technical_errors = load_artifacts(artifacts)
    if spec["task"] == "stage0_source_inventory":
        summary, metrics = collect_stage0(
            run_dir,
            spec,
            manifests,
            payloads,
            technical_errors,
            run_id=args.run_id,
            source_sha=args.source_sha,
            expected_jobs=args.expected_jobs,
            minimum_jobs=args.minimum_jobs,
            rescue=args.rescue,
            smoke=args.smoke,
        )
    elif spec["task"] == "stage1_canonicalize_verify":
        summary, metrics = collect_stage1(
            run_dir,
            spec,
            manifests,
            payloads,
            technical_errors,
            run_id=args.run_id,
            source_sha=args.source_sha,
            expected_jobs=args.expected_jobs,
            minimum_jobs=args.minimum_jobs,
            rescue=args.rescue,
            smoke=args.smoke,
        )
    else:
        raise SystemExit(f"collector does not support task: {spec['task']}")

    atomic_json(run_dir / "summary.json", summary)
    write_readme(run_dir, summary)
    checksum_lines = []
    for path in sorted(run_dir.iterdir()):
        if path.is_file() and path.name != "checksums.sha256":
            checksum_lines.append(f"{sha256(path)}  {path.name}")
    (run_dir / "checksums.sha256").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    if summary["accepted"] and not args.smoke:
        update_state_after_accepted_run(repo, spec, summary, metrics)
    elif not summary["accepted"] and not args.smoke:
        control_path = repo / "fourth-approach" / "control.json"
        control = read_json(control_path)
        control.update(
            last_run_id=args.run_id,
            last_run_index=run_index,
            last_run_accepted=False,
            recommended_next_action="inspect_failure_and_rescue_or_fix_without_advancing_stage",
        )
        atomic_json(control_path, control)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["accepted"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
