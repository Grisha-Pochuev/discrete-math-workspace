#!/usr/bin/env python3
"""Adaptive exact-certificate search for Fourth approach Run 008.

Run 008 reuses the independently checked Run-006 survivor supports but changes
the descriptor families. Every one of the 60 survivors gets one task, while the
20 strongest group-balanced survivors get a second independent task. Numerical
LSQR solutions are only leads. Exact closure requires rational reconstruction
and independent exact polynomial-identity verification on the unchanged
support.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Any


PROFILES: tuple[dict[str, Any], ...] = (
    {
        "name": "degree5_dense",
        "equation_limit": 96,
        "feature_counts": {1: 24, 2: 44, 3: 52, 4: 48, 5: 32},
        "max_iterations": 6500,
    },
    {
        "name": "degree6_sparse",
        "equation_limit": 84,
        "feature_counts": {1: 20, 2: 36, 3: 44, 4: 40, 5: 30, 6: 16},
        "max_iterations": 7000,
    },
    {
        "name": "degree6_wide",
        "equation_limit": 96,
        "feature_counts": {1: 24, 2: 40, 3: 48, 4: 44, 5: 34, 6: 20},
        "max_iterations": 7500,
    },
    {
        "name": "degree7_sparse",
        "equation_limit": 76,
        "feature_counts": {1: 18, 2: 30, 3: 36, 4: 32, 5: 24, 6: 16, 7: 8},
        "max_iterations": 8000,
    },
)
PROFILE_BY_NAME = {item["name"]: item for item in PROFILES}
GROUP_ORDER = {"old_pool": 0, "legacy_2_0": 1, "independent_2_0": 2}
DUPLICATE_QUOTAS = {"old_pool": 4, "legacy_2_0": 6, "independent_2_0": 10}
EXPECTED_CANDIDATES = 60
EXPECTED_TASKS = 80


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def read_gzip_json(path: Path) -> Any:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def write_gzip_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=9) as handle:
        json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
    os.replace(tmp, path)


def stable_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def selected_fields(record: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "slot", "candidate_key", "candidate_id", "group", "lane", "lineage_root",
        "max_error", "canonical_support_id", "nearest_exact_distance",
        "support_variables", "support_mask_hex", "support_size", "source_kind",
    )
    result = {key: record.get(key) for key in keys}
    if not isinstance(result.get("support_variables"), list) or not result["support_variables"]:
        raise ValueError(f"missing support for {result.get('candidate_key')}")
    return result


def make_task(record: dict[str, Any], task_id: int, variant: int) -> dict[str, Any]:
    slot = int(record["slot"])
    start = (slot + (2 if variant else 0)) % len(PROFILES)
    order = [PROFILES[(start + offset) % len(PROFILES)]["name"] for offset in range(len(PROFILES))]
    if variant:
        order = [order[0], order[2], order[1], order[3]]
    return {
        "task_id": task_id,
        "variant": variant,
        "seed": 8_000_011 + task_id * 1009 + variant * 104_729,
        "profile_order": order,
        "selected": selected_fields(record),
    }


def prepare_tasks(run006_results: Path) -> dict[str, Any]:
    document = read_gzip_json(run006_results)
    records = [dict(item) for item in document.get("records", []) if not bool(item.get("exact_closed", False))]
    if len(records) != EXPECTED_CANDIDATES:
        raise ValueError(f"Run 006 survivors={len(records)}, expected {EXPECTED_CANDIDATES}")
    records.sort(key=lambda item: (
        GROUP_ORDER.get(str(item.get("group")), 99),
        float(item.get("max_error", math.inf)),
        str(item.get("candidate_key")),
    ))
    tasks = [make_task(record, index, 0) for index, record in enumerate(records)]
    for group in ("old_pool", "legacy_2_0", "independent_2_0"):
        subset = [item for item in records if item.get("group") == group]
        quota = DUPLICATE_QUOTAS[group]
        if len(subset) < quota:
            raise ValueError(f"group {group} has {len(subset)}, needs {quota}")
        for record in subset[:quota]:
            tasks.append(make_task(record, len(tasks), 1))
    if len(tasks) != EXPECTED_TASKS:
        raise ValueError(f"tasks={len(tasks)}, expected {EXPECTED_TASKS}")
    payload = {
        "schema_version": 1,
        "task": "stage8_prepare_adaptive_exact_tasks",
        "source_run_006": "fourth-approach/runs/run-006-31130093117",
        "base_candidates": EXPECTED_CANDIDATES,
        "duplicate_quotas": DUPLICATE_QUOTAS,
        "task_count": len(tasks),
        "profiles": [item["name"] for item in PROFILES],
        "tasks": tasks,
    }
    payload["task_digest"] = stable_hash(payload)
    return payload


def rank(result: dict[str, Any]) -> tuple[Any, ...]:
    return (
        0 if result.get("exact_verified") else 1,
        int(result.get("nonzero_terms", 10**9)),
        float(result.get("coefficient_max", math.inf)),
        float(result.get("coefficient_rms", math.inf)),
    )


def worker_run(repo: Path, tasks_path: Path, task_id: int, seconds: int, max_attempts: int, output: Path) -> dict[str, Any]:
    import numpy as np

    base = load_module("run008_targeted", repo / "fourth-approach" / "targeted_survivors.py")
    cert, bridge = base.modules(repo)
    task_doc = read_gzip_json(tasks_path)
    tasks = list(task_doc.get("tasks", []))
    if not 0 <= task_id < len(tasks):
        raise ValueError(f"task {task_id} outside selection")
    task = dict(tasks[task_id])
    selected = dict(task["selected"])
    profiles = [PROFILE_BY_NAME[name] for name in task["profile_order"]]
    rng = np.random.default_rng(int(task["seed"]))
    started = time.time()
    deadline = started + max(60, int(seconds) - 180)
    attempts = 0
    successful = 0
    consecutive_errors = 0
    best: dict[str, Any] | None = None
    exact: dict[str, Any] | None = None
    errors: list[str] = []
    profile_attempts = {profile["name"]: 0 for profile in PROFILES}
    last_write = 0.0

    def checkpoint(force: bool = False) -> dict[str, Any]:
        nonlocal last_write
        now = time.time()
        payload = {
            "schema_version": 1,
            "task": "stage8_adaptive_exact_lemma_cycle",
            "task_digest": str(task_doc["task_digest"]),
            "task_id": task_id,
            "task_record": task,
            "attempts": attempts,
            "successful_attempts": successful,
            "profile_attempts": profile_attempts,
            "best": best,
            "exact": exact,
            "errors": errors[-40:],
            "baseline_complete": successful > 0,
            "finished": exact is not None or now >= deadline or (max_attempts > 0 and attempts >= max_attempts),
            "elapsed_seconds": now - started,
        }
        if force or now - last_write >= 20 or not output.exists():
            write_gzip_json(output, payload)
            last_write = now
        return payload

    while time.time() < deadline and (max_attempts <= 0 or attempts < max_attempts):
        attempts += 1
        if consecutive_errors >= 3:
            profile = profiles[attempts % 2]
        elif best is not None and float(best.get("coefficient_max", math.inf)) < 1e-6:
            profile = profiles[2 + (attempts % 2)]
        else:
            profile = profiles[(attempts - 1) % len(profiles)]
        profile_attempts[profile["name"]] += 1
        try:
            result = base.search_attempt(cert, bridge, rng, selected, profile)
            result["adaptive_task_variant"] = int(task["variant"])
            successful += 1
            consecutive_errors = 0
            if best is None or rank(result) < rank(best):
                best = result
            if result.get("exact_verified"):
                exact = result
                checkpoint(True)
                break
        except Exception as exc:
            consecutive_errors += 1
            errors.append(f"{type(exc).__name__}: {exc}")
        checkpoint(False)
    return checkpoint(True)


def collect(repo: Path, artifacts: Path, tasks_path: Path, run_id: int, source_sha: str) -> dict[str, Any]:
    task_doc = read_gzip_json(tasks_path)
    tasks = list(task_doc.get("tasks", []))
    if len(tasks) != EXPECTED_TASKS:
        raise ValueError(f"task count={len(tasks)}")
    digest = str(task_doc["task_digest"])
    bridge = load_module("run008_bridge", repo / "fourth-approach" / "bridge_second.py")
    workers: dict[int, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []
    for path in sorted(artifacts.rglob("worker-*.json.gz")):
        try:
            payload = read_gzip_json(path)
            task_id = int(payload["task_id"])
            if task_id in workers:
                raise ValueError(f"duplicate task {task_id}")
            if str(payload.get("task_digest")) != digest:
                raise ValueError(f"digest mismatch {task_id}")
            expected = tasks[task_id]
            actual = payload.get("task_record", {})
            if str(actual.get("selected", {}).get("candidate_key")) != str(expected.get("selected", {}).get("candidate_key")):
                raise ValueError(f"candidate mismatch {task_id}")
            if payload.get("baseline_complete") is not True or int(payload.get("successful_attempts", 0)) <= 0:
                raise ValueError(f"task {task_id} has no successful attempt")
            exact = payload.get("exact")
            if exact is not None:
                terms = bridge.deserialize_terms(list(exact.get("exact_terms") or []))
                support = [int(value) for value in expected["selected"]["support_variables"]]
                valid, error = bridge.verify_sparse_certificate(support, terms)
                if not valid:
                    raise ValueError(f"exact verification failed {task_id}: {error}")
                exact["collector_independently_verified"] = True
            workers[task_id] = payload
        except Exception as exc:
            errors.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
    missing = sorted(set(range(EXPECTED_TASKS)) - set(workers))
    if missing:
        errors.append({"missing_tasks": missing})

    task_records: list[dict[str, Any]] = []
    for task_id in sorted(workers):
        payload = workers[task_id]
        task = tasks[task_id]
        task_records.append({
            "task_id": task_id,
            "variant": int(task["variant"]),
            **dict(task["selected"]),
            "attempts": int(payload.get("attempts", 0)),
            "successful_attempts": int(payload.get("successful_attempts", 0)),
            "profile_attempts": payload.get("profile_attempts", {}),
            "best": payload.get("best"),
            "exact": payload.get("exact"),
            "exact_closed": payload.get("exact") is not None,
            "worker_errors": list(payload.get("errors", [])),
        })

    by_candidate: dict[str, dict[str, Any]] = {}
    for record in task_records:
        key = str(record["candidate_key"])
        entry = by_candidate.setdefault(key, {
            "candidate_key": key,
            "candidate_id": record.get("candidate_id"),
            "group": record.get("group"),
            "lane": record.get("lane"),
            "lineage_root": record.get("lineage_root"),
            "max_error": record.get("max_error"),
            "support_size": record.get("support_size"),
            "task_ids": [],
            "exact_closed": False,
            "exact_tasks": [],
            "best_coefficient_max": None,
            "best_profile": None,
        })
        entry["task_ids"].append(record["task_id"])
        if record["exact_closed"]:
            entry["exact_closed"] = True
            entry["exact_tasks"].append(record["task_id"])
        best = record.get("best") or {}
        value = best.get("coefficient_max")
        if value is not None and math.isfinite(float(value)):
            if entry["best_coefficient_max"] is None or float(value) < float(entry["best_coefficient_max"]):
                entry["best_coefficient_max"] = float(value)
                entry["best_profile"] = best.get("profile")
    candidates = sorted(by_candidate.values(), key=lambda item: (
        GROUP_ORDER.get(str(item.get("group")), 99),
        bool(item.get("exact_closed")),
        float(item.get("max_error", math.inf)),
        str(item.get("candidate_key")),
    ))
    exact_candidates = [item for item in candidates if item["exact_closed"]]
    survivors = [item for item in candidates if not item["exact_closed"]]
    groups = {}
    for group in ("old_pool", "legacy_2_0", "independent_2_0"):
        subset = [item for item in candidates if item.get("group") == group]
        exact_subset = [item for item in subset if item["exact_closed"]]
        groups[group] = {
            "candidates": len(subset),
            "exactly_closed": len(exact_subset),
            "survivors": len(subset) - len(exact_subset),
            "duplicate_covered": sum(len(item["task_ids"]) > 1 for item in subset),
            "best_input_max_error": min((float(item["max_error"]) for item in subset), default=None),
        }

    accepted = len(workers) == EXPECTED_TASKS and not errors and len(candidates) == EXPECTED_CANDIDATES
    metrics = {
        "jobs_configured": 20,
        "workers_expected": EXPECTED_TASKS,
        "workers_present": len(workers),
        "candidate_count": len(candidates),
        "duplicate_tasks": EXPECTED_TASKS - EXPECTED_CANDIDATES,
        "exact_task_closures": sum(bool(item["exact_closed"]) for item in task_records),
        "exact_candidate_closures": len(exact_candidates),
        "survivor_candidates": len(survivors),
        "total_attempts": sum(int(item["attempts"]) for item in task_records),
        "successful_attempts": sum(int(item["successful_attempts"]) for item in task_records),
        "worker_error_count": len(errors),
        "groups": groups,
    }
    run_dir = repo / "fourth-approach" / "runs" / f"run-008-{run_id}"
    if run_dir.exists():
        return read_json(run_dir / "summary.json")
    run_dir.mkdir(parents=True)
    write_gzip_json(run_dir / "adaptive-task-results.json.gz", {
        "schema_version": 1,
        "task_digest": digest,
        "records": task_records,
        "collector_errors": errors,
    })
    write_json(run_dir / "candidate-results.json", {"schema_version": 1, "candidates": candidates})
    write_json(run_dir / "exact-closures.json", {
        "schema_version": 1,
        "scope": "independently reverified exact certificates on unchanged Run-006 survivor supports",
        "candidates": exact_candidates,
    })
    write_json(run_dir / "survivors.json", {
        "schema_version": 1,
        "scope": "survived the recorded adaptive degree-5/6/7 bounded search only; not counterexamples",
        "candidates": survivors,
    })
    robust = sorted(survivors, key=lambda item: (-len(item["task_ids"]), float(item["max_error"]), str(item["candidate_key"])))
    write_json(run_dir / "gpt-sol-handoff.json", {
        "schema_version": 1,
        "purpose": "post-Run-008 evidence for GPT-5.6 Sol",
        "exact_candidate_closures": exact_candidates[:20],
        "robust_survivors": robust[:30],
        "interpretation": "A robust survivor has one or two completed adaptive tasks but remains only a bounded negative result, never a counterexample.",
        "next_question": "Which support-local invariant explains exact Run-004 obstruction classes while surviving the Run-005/006/008 falsification data?",
    })
    write_json(run_dir / "worker-validation.json", {"task_digest": digest, "workers_present": len(workers), "errors": errors})
    summary = {
        "schema_version": 1,
        "approach": "fourth-approach-obstruction-guided-exact-synthesis",
        "accepted": accepted,
        "run_id": run_id,
        "run_index": 8,
        "task": "stage8_adaptive_exact_lemma_cycle",
        "source_sha": source_sha,
        "metrics": metrics,
        "scientific_interpretation": "Adaptive degree-5/6/7 descriptor search. Exact closures are independently reverified; nonclosures are bounded negative evidence only.",
        "next_decision": "Review the post-Run-008 Sol handoff before selecting a structural lemma test or n=8 transfer.",
    }
    write_json(run_dir / "summary.json", summary)
    checks = []
    for path in sorted(run_dir.iterdir()):
        if path.is_file() and path.name != "checksums.sha256":
            checks.append(f"{sha256(path)}  {path.name}")
    (run_dir / "checksums.sha256").write_text("\n".join(checks) + "\n", encoding="utf-8")

    control_path = repo / "fourth-approach" / "control.json"
    launch_path = repo / "fourth-approach" / "launch.json"
    control = read_json(control_path)
    history = list(control.get("run_history", []))
    history.append({"accepted": accepted, "run_id": run_id, "run_index": 8, "task": "stage8_adaptive_exact_lemma_cycle", "metrics": metrics})
    if accepted:
        control.update(
            completed_runs=int(control.get("completed_runs", 0)) + 1,
            current_stage=9,
            current_stage_name="post_adaptive_structural_decision",
            last_run_id=run_id,
            last_run_index=8,
            last_run_accepted=True,
            next_run_index=9,
            next_task="stage9_structural_decision",
            next_spec_path="fourth-approach/run-specs/run-009-stage9-structural-decision.json",
            recommended_next_action="review_run_008_sol_handoff_before_any_n8_transfer",
            scientific_stopping_rule="manual GPT-5.6 Sol review before n=8 transfer",
            minimum_free_concurrency_slots=0,
            run_history=history,
        )
    else:
        control.update(
            last_run_id=run_id,
            last_run_index=8,
            last_run_accepted=False,
            recommended_next_action="inspect_or_rescue_run_008_without_advancing",
            run_history=history,
        )
    write_json(control_path, control)
    write_json(launch_path, {
        "schema_version": 1,
        "enabled": False,
        "run_index": 8,
        "task": "stage8_adaptive_exact_lemma_cycle",
        "spec_path": "fourth-approach/run-specs/run-008-stage8-adaptive-exact-lemma-cycle.json",
        "jobs": 20,
        "minimum_jobs": 20,
        "runtime_seconds": 20400,
        "max_attempts": 0,
        "nonce": f"fourth-run-008-completed-{run_id}",
    })
    return summary


def self_test() -> None:
    records = []
    slot = 0
    for group, count in (("old_pool", 10), ("legacy_2_0", 20), ("independent_2_0", 30)):
        for index in range(count):
            records.append({
                "slot": slot,
                "candidate_key": f"{group}-{index}",
                "candidate_id": f"c-{slot}",
                "group": group,
                "lane": "test",
                "lineage_root": f"l-{slot}",
                "max_error": 1e-6 + slot * 1e-8,
                "canonical_support_id": f"s-{slot}",
                "nearest_exact_distance": -1,
                "support_variables": list(range(10 + slot % 3)),
                "support_mask_hex": "0x0",
                "support_size": 10 + slot % 3,
                "source_kind": "test",
                "exact_closed": False,
            })
            slot += 1
    tasks = [make_task(record, index, 0) for index, record in enumerate(records)]
    for group in ("old_pool", "legacy_2_0", "independent_2_0"):
        subset = [item for item in records if item["group"] == group][:DUPLICATE_QUOTAS[group]]
        for record in subset:
            tasks.append(make_task(record, len(tasks), 1))
    assert len(tasks) == EXPECTED_TASKS
    assert len({task["task_id"] for task in tasks}) == EXPECTED_TASKS
    assert set(PROFILE_BY_NAME) == {"degree5_dense", "degree6_sparse", "degree6_wide", "degree7_sparse"}
    print(json.dumps({"self_test": "ok", "tasks": len(tasks), "profiles": list(PROFILE_BY_NAME)}))


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--run006-results", type=Path, required=True)
    prep.add_argument("--output", type=Path, required=True)
    worker = sub.add_parser("worker")
    worker.add_argument("--repo", type=Path, default=Path("."))
    worker.add_argument("--tasks", type=Path, required=True)
    worker.add_argument("--task-id", type=int, required=True)
    worker.add_argument("--seconds", type=int, default=20400)
    worker.add_argument("--max-attempts", type=int, default=0)
    worker.add_argument("--output", type=Path, required=True)
    coll = sub.add_parser("collect")
    coll.add_argument("--repo", type=Path, default=Path("."))
    coll.add_argument("--artifacts", type=Path, required=True)
    coll.add_argument("--tasks", type=Path, required=True)
    coll.add_argument("--run-id", type=int, required=True)
    coll.add_argument("--source-sha", required=True)
    sub.add_parser("self-test")
    args = parser.parse_args()

    if args.command == "self-test":
        self_test()
        return 0
    if args.command == "prepare":
        payload = prepare_tasks(args.run006_results.resolve())
        write_gzip_json(args.output.resolve(), payload)
        print(json.dumps({"task_count": payload["task_count"], "task_digest": payload["task_digest"]}, indent=2))
        return 0
    if args.command == "worker":
        payload = worker_run(args.repo.resolve(), args.tasks.resolve(), args.task_id, args.seconds, args.max_attempts, args.output.resolve())
        print(json.dumps({"task_id": payload["task_id"], "attempts": payload["attempts"], "successful_attempts": payload["successful_attempts"], "exact": payload["exact"] is not None}, indent=2))
        return 0 if payload["baseline_complete"] else 3
    summary = collect(args.repo.resolve(), args.artifacts.resolve(), args.tasks.resolve(), args.run_id, args.source_sha)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary.get("accepted") else 3


if __name__ == "__main__":
    raise SystemExit(main())
