#!/usr/bin/env python3
"""Collect and independently validate Fourth approach Run 005 bridge outputs."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def read_gzip_json(path: Path) -> Any:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def write_gzip_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with gzip.open(temporary, "wt", encoding="utf-8", compresslevel=9) as handle:
        json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
    os.replace(temporary, path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def best_error(records: list[dict[str, Any]]) -> float | None:
    finite = [float(item.get("max_error", math.inf)) for item in records if math.isfinite(float(item.get("max_error", math.inf)))]
    return min(finite) if finite else None


def covered(record: dict[str, Any]) -> bool:
    return record.get("baseline_coverage") is not None or record.get("orbit_coverage") is not None


def nearest_distance(record: dict[str, Any]) -> int | None:
    if record.get("orbit_nearest"):
        return int(record["orbit_nearest"][0]["distance"])
    if record.get("nearest_canonical"):
        return int(record["nearest_canonical"][0]["distance"])
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--expected-workers", type=int, default=80)
    args = parser.parse_args()

    repo = args.repo.resolve()
    prepared = read_gzip_json(args.prepared.resolve())
    payload_paths = sorted(args.artifacts.rglob("worker-*.json.gz"))
    errors: list[dict[str, Any]] = []
    lanes: set[int] = set()
    records_by_key: dict[str, dict[str, Any]] = {}
    global_counts: set[int] = set()
    for path in payload_paths:
        try:
            payload = read_gzip_json(path)
        except Exception as exc:
            errors.append({"path": str(path), "error": f"unreadable payload: {exc}"})
            continue
        if payload.get("task") != "stage5_bridge_second_approach":
            errors.append({"path": str(path), "error": "wrong task"})
            continue
        lane_id = int(payload.get("lane_id", -1))
        if lane_id in lanes:
            errors.append({"path": str(path), "error": f"duplicate lane {lane_id}"})
        lanes.add(lane_id)
        global_counts.add(int(payload.get("global_candidate_count", -1)))
        if payload.get("baseline_complete") is not True:
            errors.append({"path": str(path), "error": "baseline incomplete"})
        assigned = int(payload.get("assigned_candidates", -1))
        records = list(payload.get("records", []))
        if assigned != len(records):
            errors.append({"path": str(path), "error": f"assigned={assigned} records={len(records)}"})
        for record in records:
            key = str(record.get("candidate_key", ""))
            if not key:
                errors.append({"path": str(path), "error": "record without candidate_key"})
                continue
            previous = records_by_key.get(key)
            if previous is not None and previous != record:
                errors.append({"candidate_key": key, "error": "conflicting duplicate record"})
            records_by_key[key] = record

    global_count = next(iter(global_counts)) if len(global_counts) == 1 else -1
    records = [records_by_key[key] for key in sorted(records_by_key)]
    full_coverage = global_count >= 0 and len(records) == global_count
    expected_lanes = set(range(int(args.expected_workers)))
    all_workers_present = lanes == expected_lanes

    groups: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        groups.setdefault(str(record.get("group", "unknown")), []).append(record)

    group_metrics: dict[str, dict[str, Any]] = {}
    for group, subset in sorted(groups.items()):
        covered_records = [item for item in subset if covered(item)]
        hard = [item for item in subset if not covered(item)]
        orbit_complete = [item for item in subset if item.get("orbit_scan_complete") is True]
        group_metrics[group] = {
            "candidates": len(subset),
            "exactly_covered": len(covered_records),
            "coverage_fraction": len(covered_records) / len(subset) if subset else 0.0,
            "hard_survivors": len(hard),
            "orbit_scans_complete": len(orbit_complete),
            "radius1_scans_complete": sum(item.get("radius1_complete") is True for item in subset),
            "radius1_exact_hits": sum(len(item.get("radius1_exact_hits", [])) for item in subset),
            "radius2_samples": sum(int(item.get("radius2_samples", 0)) for item in subset),
            "radius2_exact_hits": sum(len(item.get("radius2_exact_hits", [])) for item in subset),
            "best_max_error": best_error(subset),
            "best_covered_max_error": best_error(covered_records),
            "best_hard_survivor_max_error": best_error(hard),
        }

    hard_survivors = sorted(
        [item for item in records if not covered(item)],
        key=lambda item: (
            0 if item.get("group") == "old_pool" else 1 if item.get("group") == "legacy_2_0" else 2,
            float(item.get("max_error", math.inf)),
            nearest_distance(item) if nearest_distance(item) is not None else 10**9,
            item["candidate_key"],
        ),
    )
    compact_hard = [
        {
            "candidate_key": item["candidate_key"],
            "candidate_id": item.get("candidate_id"),
            "group": item.get("group"),
            "max_error": item.get("max_error"),
            "support_size": item.get("support_size"),
            "canonical_support_id": item.get("canonical_support_id"),
            "nearest_exact_distance": nearest_distance(item),
            "orbit_scan_complete": item.get("orbit_scan_complete"),
            "radius1_complete": item.get("radius1_complete"),
            "radius1_exact_hits": item.get("radius1_exact_hits", [])[:8],
            "radius2_samples": item.get("radius2_samples", 0),
            "radius2_exact_hits": item.get("radius2_exact_hits", [])[:8],
            "lineage_root": item.get("lineage_root"),
            "lane": item.get("lane"),
        }
        for item in hard_survivors[:200]
    ]

    accepted = (
        not errors
        and all_workers_present
        and full_coverage
        and len(records) > 0
        and int(prepared.get("source_run004_records", 0)) == 2594
        and int(prepared.get("support_classes", 0)) == 2594
    )
    run_dir = repo / "fourth-approach" / "runs" / f"run-005-{args.run_id}"
    if run_dir.exists():
        raise SystemExit(f"refusing to overwrite {run_dir}")
    run_dir.mkdir(parents=True)
    write_gzip_json(run_dir / "bridge-records.json.gz", {
        "schema_version": 1,
        "task": "stage5_bridge_second_approach",
        "records": records,
    })
    write_json(run_dir / "hard-survivors.json", {
        "schema_version": 1,
        "scope": "not covered by tested Run-004 exact certificate mechanisms; not evidence of a counterexample",
        "survivors": compact_hard,
    })
    write_json(run_dir / "mechanism-library-summary.json", {
        "schema_version": 1,
        "source_run004_records": prepared.get("source_run004_records"),
        "support_classes": prepared.get("support_classes"),
        "canonical_mechanism_classes": prepared.get("canonical_mechanism_classes"),
    })
    write_json(run_dir / "worker-validation.json", {
        "expected_workers": args.expected_workers,
        "worker_payloads_found": len(payload_paths),
        "lane_ids": sorted(lanes),
        "errors": errors,
    })
    metrics = {
        "candidate_records": len(records),
        "global_candidate_count": global_count,
        "full_candidate_coverage": full_coverage,
        "workers_present": len(lanes),
        "canonical_mechanism_classes": int(prepared.get("canonical_mechanism_classes", 0)),
        "exact_support_classes": int(prepared.get("support_classes", 0)),
        "exactly_covered_candidates": sum(covered(item) for item in records),
        "hard_survivors": len(hard_survivors),
        "orbit_scans_complete": sum(item.get("orbit_scan_complete") is True for item in records),
        "radius1_scans_complete": sum(item.get("radius1_complete") is True for item in records),
        "radius1_exact_hits": sum(len(item.get("radius1_exact_hits", [])) for item in records),
        "radius2_samples": sum(int(item.get("radius2_samples", 0)) for item in records),
        "radius2_exact_hits": sum(len(item.get("radius2_exact_hits", [])) for item in records),
        "groups": group_metrics,
    }
    summary = {
        "schema_version": 1,
        "approach": "fourth-approach-obstruction-guided-exact-synthesis",
        "accepted": accepted,
        "run_id": args.run_id,
        "run_index": 5,
        "task": "stage5_bridge_second_approach",
        "source_sha": args.source_sha,
        "worker_error_count": len(errors),
        "metrics": metrics,
        "scientific_interpretation": (
            "Coverage means an exact rational Run-004 certificate was re-verified on the numerical candidate support, possibly after an explicit S6 x S3 alignment. "
            "Uncovered candidates are hard survivors only relative to the tested certificate library and explored support neighborhoods; they are not counterexamples."
        ),
        "next_decision": "Use the strongest separately reported old-pool and independent hard survivors for targeted higher-degree exact tests and a compact GPT-5.6 Sol handoff.",
    }
    write_json(run_dir / "summary.json", summary)
    (run_dir / "README.md").write_text(
        "# Fourth approach Run 005\n\n"
        f"- GitHub Actions run: `{args.run_id}`\n"
        f"- Accepted: `{accepted}`\n"
        f"- Candidate records: `{len(records)}/{global_count}`\n"
        f"- Exact mechanism classes: `{prepared.get('canonical_mechanism_classes')}`\n"
        f"- Exactly covered candidates: `{metrics['exactly_covered_candidates']}`\n"
        f"- Hard survivors relative to tested library: `{metrics['hard_survivors']}`\n\n"
        "A hard survivor is not a counterexample. It is only a candidate not closed by the tested compact exact mechanisms and neighborhoods.\n",
        encoding="utf-8",
    )
    checksum_lines = []
    for path in sorted(run_dir.iterdir()):
        if path.is_file() and path.name != "checksums.sha256":
            checksum_lines.append(f"{sha256(path)}  {path.name}")
    (run_dir / "checksums.sha256").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    control_path = repo / "fourth-approach" / "control.json"
    launch_path = repo / "fourth-approach" / "launch.json"
    control = read_json(control_path)
    history = list(control.get("run_history", []))
    history.append({
        "run_id": args.run_id,
        "run_index": 5,
        "task": "stage5_bridge_second_approach",
        "accepted": accepted,
        "metrics": metrics,
    })
    control.update(
        completed_runs=int(control.get("completed_runs", 0)) + (1 if accepted else 0),
        last_run_id=args.run_id,
        last_run_index=5,
        last_run_accepted=accepted,
        current_stage=6 if accepted else 5,
        current_stage_name="targeted_hard_survivor_exact_tests" if accepted else "bridge_second_approach_repair",
        next_run_index=6 if accepted else 5,
        next_task="stage6_targeted_hard_survivors" if accepted else "stage5_bridge_second_approach",
        next_spec_path="fourth-approach/run-specs/run-006-stage6-targeted-hard-survivors.json" if accepted else "fourth-approach/run-specs/run-005-stage5-bridge-second-approach.json",
        recommended_next_action="design_targeted_higher_degree_tests_and_sol_handoff" if accepted else "inspect_run005_failure_without_launching_successor",
        run_history=history,
        tracking_enabled=False,
        full_run_auto_launch_allowed=False,
    )
    write_json(control_path, control)
    write_json(launch_path, {
        "schema_version": 1,
        "enabled": False,
        "run_index": 5,
        "task": "stage5_bridge_second_approach",
        "spec_path": "fourth-approach/run-specs/run-005-stage5-bridge-second-approach.json",
        "jobs": 20,
        "minimum_jobs": 20,
        "runtime_seconds": 20700,
        "max_attempts": 0,
        "nonce": f"fourth-run-005-completed-{args.run_id}",
    })
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if accepted else 3


if __name__ == "__main__":
    raise SystemExit(main())
