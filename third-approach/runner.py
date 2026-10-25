#!/usr/bin/env python3
"""Checkpointed four-process driver for the third, proof-oriented approach."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import signal
import socket
import time
import traceback
from typing import Any

import numpy as np

from certificate import search_once, shape_for


DEFAULT_POLICY = {
    "fresh_fraction": 0.45,
    "elite_mutation_fraction": 0.35,
    "diverse_mutation_fraction": 0.20,
    "elite_mutation_min": 0.08,
    "elite_mutation_max": 0.20,
    "diverse_mutation_min": 0.25,
    "diverse_mutation_max": 0.50,
    "elite_parent_limit": 300,
}


def atomic_json(path: Path, document: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def append_jsonl(path: Path, document: dict) -> None:
    with path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n")
        out.flush()
        os.fsync(out.fileno())


def read_gzip_json(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as source:
        return json.load(source)


def load_candidate_bank(repo: Path) -> tuple[list[dict[str, Any]], str | None]:
    path = repo / "third-approach" / "candidates" / "bank.json.gz"
    if not path.exists():
        return [], None
    try:
        document = read_gzip_json(path)
        candidates = []
        for item in document.get("candidates", []):
            try:
                score = float(item["certificate_score"])
                support = list(item["support_variables"])
            except Exception:
                continue
            if math.isfinite(score) and support:
                candidates.append(item)
        candidates.sort(key=lambda item: float(item["certificate_score"]))
        return candidates, None
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"


def normalized_policy(launch: dict, bank_size: int) -> dict[str, float | int]:
    supplied = launch.get("search_policy", {})
    policy = dict(DEFAULT_POLICY)
    if isinstance(supplied, dict):
        for key in policy:
            if key in supplied:
                policy[key] = supplied[key]

    fresh = max(0.35, float(policy["fresh_fraction"]))
    elite = min(0.45, max(0.0, float(policy["elite_mutation_fraction"])))
    diverse = max(0.15, float(policy["diverse_mutation_fraction"]))
    if bank_size == 0:
        fresh, elite, diverse = 1.0, 0.0, 0.0
    else:
        total = fresh + elite + diverse
        fresh, elite, diverse = fresh / total, elite / total, diverse / total
        if fresh < 0.35:
            remainder = 0.65
            split = elite + diverse
            fresh = 0.35
            elite = remainder * elite / split
            diverse = remainder * diverse / split

    e_min = float(np.clip(policy["elite_mutation_min"], 0.02, 0.50))
    e_max = float(np.clip(policy["elite_mutation_max"], e_min, 0.70))
    d_min = float(np.clip(policy["diverse_mutation_min"], 0.08, 0.70))
    d_max = float(np.clip(policy["diverse_mutation_max"], d_min, 0.85))
    return {
        "fresh_fraction": fresh,
        "elite_mutation_fraction": elite,
        "diverse_mutation_fraction": diverse,
        "elite_mutation_min": e_min,
        "elite_mutation_max": e_max,
        "diverse_mutation_min": d_min,
        "diverse_mutation_max": d_max,
        "elite_parent_limit": max(20, int(policy["elite_parent_limit"])),
    }


def structural_bucket(item: dict[str, Any]) -> tuple[int, int, int]:
    return (
        int(item.get("support_size", len(item.get("support_variables", [])))) // 3,
        len(item.get("equation_rows", [])) // 4,
        len(item.get("multiplier_positions", [])) // 2,
    )


def rank_weighted_choice(
    rng: np.random.Generator, candidates: list[dict[str, Any]]
) -> dict[str, Any]:
    if len(candidates) == 1:
        return candidates[0]
    weights = 1.0 / np.sqrt(np.arange(1, len(candidates) + 1, dtype=float))
    weights /= weights.sum()
    return candidates[int(rng.choice(len(candidates), p=weights))]


def select_parent(
    rng: np.random.Generator,
    bank: list[dict[str, Any]],
    mode: str,
    policy: dict[str, float | int],
) -> dict[str, Any]:
    if mode == "elite_mutation":
        limit = min(len(bank), int(policy["elite_parent_limit"]))
        return rank_weighted_choice(rng, bank[:limit])

    groups: dict[tuple[int, int, int], list[dict[str, Any]]] = defaultdict(list)
    for item in bank:
        groups[structural_bucket(item)].append(item)
    keys = list(groups)
    key = keys[int(rng.integers(0, len(keys)))]
    group = sorted(groups[key], key=lambda item: float(item["certificate_score"]))
    return rank_weighted_choice(rng, group)


def choose_mode(
    rng: np.random.Generator,
    bank: list[dict[str, Any]],
    policy: dict[str, float | int],
) -> str:
    if not bank:
        return "fresh"
    draw = float(rng.random())
    fresh = float(policy["fresh_fraction"])
    elite = float(policy["elite_mutation_fraction"])
    if draw < fresh:
        return "fresh"
    if draw < fresh + elite:
        return "elite_mutation"
    return "diverse_mutation"


def mutation_fraction(
    rng: np.random.Generator, mode: str, policy: dict[str, float | int]
) -> float:
    if mode == "elite_mutation":
        return float(
            rng.uniform(
                float(policy["elite_mutation_min"]),
                float(policy["elite_mutation_max"]),
            )
        )
    if mode == "diverse_mutation":
        return float(
            rng.uniform(
                float(policy["diverse_mutation_min"]),
                float(policy["diverse_mutation_max"]),
            )
        )
    return 0.0


def worker_main(
    repo: str,
    output: str,
    run_index: int,
    job_id: int,
    worker_id: int,
    base_seed: int,
    deadline: float,
    max_attempts: int,
    policy: dict[str, float | int],
) -> None:
    repo_path = Path(repo)
    root = Path(output) / f"worker-{worker_id}"
    root.mkdir(parents=True, exist_ok=True)
    metrics_path = root / "metrics.jsonl"
    rng = np.random.default_rng(
        base_seed + run_index * 10_000_019 + job_id * 100_003 + worker_id * 1_009
    )
    shape = shape_for(job_id, worker_id, run_index)
    bank, bank_error = load_candidate_bank(repo_path)
    best: list[tuple[float, str]] = []
    attempt = 0
    errors = 0
    mode_counts: Counter[str] = Counter()
    parent_counts: Counter[str] = Counter()
    started = time.time()

    if bank_error:
        append_jsonl(
            root / "warnings.jsonl",
            {"warning": "candidate_bank_unreadable", "message": bank_error},
        )

    while time.time() < deadline and (max_attempts <= 0 or attempt < max_attempts):
        attempt_started = time.time()
        try:
            mode = choose_mode(rng, bank, policy)
            parent = None if mode == "fresh" else select_parent(rng, bank, mode, policy)
            mutation = mutation_fraction(rng, mode, policy)
            result = search_once(
                rng,
                shape,
                parent=parent,
                search_mode=mode,
                mutation_fraction=mutation,
            )
            candidate_id = f"r{run_index:03d}-j{job_id:02d}-w{worker_id}-a{attempt:06d}"
            result.update(
                {
                    "candidate_id": candidate_id,
                    "run_index": run_index,
                    "job_id": job_id,
                    "worker_id": worker_id,
                    "attempt": attempt,
                    "elapsed_seconds": time.time() - attempt_started,
                }
            )
            mode_counts[mode] += 1
            if parent is not None:
                parent_counts[str(parent.get("candidate_id", "unknown"))] += 1

            append_jsonl(
                metrics_path,
                {
                    "attempt": attempt,
                    "candidate_id": candidate_id,
                    "certificate_score": result["certificate_score"],
                    "train_rms": result["train_rms"],
                    "validation_rms": result["validation_rms"],
                    "validation_max": result["validation_max"],
                    "support_size": result["support_size"],
                    "feature_count": result["feature_count"],
                    "search_mode": mode,
                    "parent_candidate_id": result["parent_candidate_id"],
                    "support_distance_from_parent": result[
                        "support_distance_from_parent"
                    ],
                    "elapsed_seconds": result["elapsed_seconds"],
                },
            )
            score = float(result["certificate_score"])
            if len(best) < 5 or score < max(item[0] for item in best):
                candidate_path = root / f"candidate-{candidate_id}.json.gz"
                with gzip.open(candidate_path, "wt", encoding="utf-8") as out:
                    json.dump(result, out, sort_keys=True, separators=(",", ":"))
                    out.write("\n")
                best.append((score, candidate_path.name))
                best.sort()
                while len(best) > 5:
                    _, old_name = best.pop()
                    old = root / old_name
                    if old.exists():
                        old.unlink()
        except BaseException as exc:
            errors += 1
            append_jsonl(
                root / "errors.jsonl",
                {
                    "attempt": attempt,
                    "error": type(exc).__name__,
                    "message": str(exc),
                    "traceback": traceback.format_exc(),
                },
            )

        attempt += 1
        atomic_json(
            root / "checkpoint.json",
            {
                "worker_id": worker_id,
                "attempts": attempt,
                "errors": errors,
                "started_at": started,
                "updated_at": time.time(),
                "deadline": deadline,
                "best_score": best[0][0] if best else None,
                "shape": shape.__dict__,
                "bank_size": len(bank),
                "bank_load_error": bank_error,
                "search_policy": policy,
                "search_mode_counts": dict(mode_counts),
                "distinct_parents_used": len(parent_counts),
            },
        )

    atomic_json(
        root / "complete.json",
        {
            "worker_id": worker_id,
            "attempts": attempt,
            "errors": errors,
            "started_at": started,
            "finished_at": time.time(),
            "stop_reason": "deadline" if time.time() >= deadline else "attempt_cap",
            "best_score": best[0][0] if best else None,
            "shape": shape.__dict__,
            "bank_size": len(bank),
            "bank_load_error": bank_error,
            "search_policy": policy,
            "search_mode_counts": dict(mode_counts),
            "distinct_parents_used": len(parent_counts),
        },
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-id", type=int, required=True)
    ap.add_argument("--run-index", type=int, required=True)
    ap.add_argument("--base-seed", type=int, required=True)
    ap.add_argument("--seconds", type=int, default=21000)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max-attempts", type=int, default=0)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    repo = Path(__file__).resolve().parents[1]
    launch = json.loads((repo / "third-approach" / "launch.json").read_text())
    bank, bank_error = load_candidate_bank(repo)
    policy = normalized_policy(launch, len(bank))

    start = time.time()
    reserve = 480 if args.seconds >= 1800 else max(10, args.seconds // 5)
    deadline = start + max(20, args.seconds - reserve)
    processes: list[mp.Process] = []
    for worker_id in range(args.workers):
        process = mp.Process(
            target=worker_main,
            args=(
                str(repo),
                str(args.output),
                args.run_index,
                args.job_id,
                worker_id,
                args.base_seed,
                deadline,
                args.max_attempts,
                policy,
            ),
            daemon=False,
        )
        process.start()
        processes.append(process)

    while time.time() < deadline and any(p.is_alive() for p in processes):
        time.sleep(3)
    for process in processes:
        if process.is_alive():
            process.terminate()
    for process in processes:
        process.join(timeout=30)
        if process.is_alive():
            os.kill(process.pid, signal.SIGKILL)
            process.join(timeout=5)

    workers = []
    for worker_id, process in enumerate(processes):
        complete = args.output / f"worker-{worker_id}" / "complete.json"
        checkpoint = args.output / f"worker-{worker_id}" / "checkpoint.json"
        source = complete if complete.exists() else checkpoint
        info = json.loads(source.read_text()) if source.exists() else {}
        info["exitcode"] = process.exitcode
        workers.append(info)

    aggregate_modes: Counter[str] = Counter()
    for worker in workers:
        aggregate_modes.update(worker.get("search_mode_counts", {}))

    manifest = {
        "schema_version": 2,
        "approach": "third-proof-oriented-numerical-certificates",
        "run_index": args.run_index,
        "job_id": args.job_id,
        "base_seed": args.base_seed,
        "workers": args.workers,
        "max_attempts_per_worker": args.max_attempts,
        "stopping_policy": (
            "time_only" if args.max_attempts <= 0 else "time_or_attempt_cap"
        ),
        "requested_runtime_seconds": args.seconds,
        "effective_deadline_seconds": max(20, args.seconds - reserve),
        "hostname": socket.gethostname(),
        "started_at": start,
        "finished_at": time.time(),
        "candidate_bank_size": len(bank),
        "candidate_bank_load_error": bank_error,
        "search_policy": policy,
        "search_mode_counts": dict(aggregate_modes),
        "worker_manifests": workers,
    }
    atomic_json(args.output / "manifest.json", manifest)
    return 0 if any(w.get("best_score") is not None for w in workers) else 2


if __name__ == "__main__":
    raise SystemExit(main())
