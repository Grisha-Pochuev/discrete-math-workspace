#!/usr/bin/env python3
"""Checkpointed multi-basin driver for Third approach 2.0."""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
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

PROFILE_WEIGHTS: dict[str, dict[str, float]] = {
    "balanced": {
        "fresh": 0.30,
        "elite_refine": 0.20,
        "basin_refine": 0.20,
        "degree_expand": 0.15,
        "support_escape": 0.08,
        "contrast_focus": 0.07,
    },
    "multi_basin": {
        "fresh": 0.25,
        "elite_refine": 0.10,
        "basin_refine": 0.35,
        "degree_expand": 0.10,
        "support_escape": 0.10,
        "contrast_focus": 0.10,
    },
    "degree_expand": {
        "fresh": 0.18,
        "elite_refine": 0.12,
        "basin_refine": 0.15,
        "degree_expand": 0.40,
        "support_escape": 0.07,
        "contrast_focus": 0.08,
    },
    "support_escape": {
        "fresh": 0.25,
        "elite_refine": 0.08,
        "basin_refine": 0.12,
        "degree_expand": 0.10,
        "support_escape": 0.35,
        "contrast_focus": 0.10,
    },
    "contrast_focus": {
        "fresh": 0.18,
        "elite_refine": 0.12,
        "basin_refine": 0.18,
        "degree_expand": 0.12,
        "support_escape": 0.10,
        "contrast_focus": 0.30,
    },
    "exact_reconstruction": {
        "fresh": 0.15,
        "elite_refine": 0.32,
        "basin_refine": 0.18,
        "degree_expand": 0.12,
        "support_escape": 0.05,
        "contrast_focus": 0.18,
    },
}

ELITE_LIMIT = 32
EXACT_LIMIT = 16
BASIN_BUCKETS = 16
LINEAGE_BUCKETS = 16
MAX_RETAINED_PER_WORKER = ELITE_LIMIT + EXACT_LIMIT + BASIN_BUCKETS + LINEAGE_BUCKETS
LONG_RUN_SHUTDOWN_RESERVE_SECONDS = 600


def atomic_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def append_jsonl(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n")
        out.flush()
        os.fsync(out.fileno())


def read_gzip_json(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as source:
        return json.load(source)


def load_candidate_bank(repo: Path) -> tuple[list[dict[str, Any]], str | None]:
    path = repo / "third-approach-2.0" / "candidates" / "bank.json.gz"
    if not path.exists():
        return [], None
    try:
        document = read_gzip_json(path)
        candidates = []
        for item in document.get("candidates", []):
            try:
                value = float(item["certificate_score"])
                support = list(item["support_variables"])
            except Exception:
                continue
            if math.isfinite(value) and support:
                candidates.append(item)
        candidates.sort(key=lambda item: float(item["certificate_score"]))
        return candidates, None
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"


def normalize_weights(profile: str, bank_size: int, launch: dict[str, Any]) -> dict[str, float]:
    if profile not in PROFILE_WEIGHTS:
        raise ValueError(f"unsupported strategy profile: {profile}")
    weights = dict(PROFILE_WEIGHTS[profile])
    supplied = launch.get("lane_weights")
    if isinstance(supplied, dict):
        if set(supplied) != set(weights):
            raise ValueError("lane_weights must define exactly the six supported lanes")
        for lane in weights:
            weights[lane] = max(0.0, float(supplied[lane]))
    if bank_size == 0:
        return {lane: (1.0 if lane == "fresh" else 0.0) for lane in weights}
    weights["fresh"] = max(0.15, weights["fresh"])
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("lane weights have zero total")
    return {lane: value / total for lane, value in weights.items()}


def weighted_lane(rng: np.random.Generator, weights: dict[str, float]) -> str:
    lanes = list(weights)
    probabilities = np.asarray([weights[lane] for lane in lanes], dtype=float)
    probabilities /= probabilities.sum()
    return lanes[int(rng.choice(len(lanes), p=probabilities))]


def rank_choice(rng: np.random.Generator, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    if len(candidates) == 1:
        return candidates[0]
    weights = 1.0 / np.sqrt(np.arange(1, len(candidates) + 1, dtype=float))
    weights /= weights.sum()
    return candidates[int(rng.choice(len(candidates), p=weights))]


def basin_champions(bank: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for item in bank:
        basin = str(item.get("basin_fingerprint", item.get("support_fingerprint", "unknown")))
        if basin not in best or float(item["certificate_score"]) < float(best[basin]["certificate_score"]):
            best[basin] = item
    return sorted(best.values(), key=lambda item: float(item["certificate_score"]))


def lineage_champions(bank: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for item in bank:
        root = str(item.get("lineage_root", item.get("candidate_id", "unknown")))
        if root not in best or float(item["certificate_score"]) < float(best[root]["certificate_score"]):
            best[root] = item
    return sorted(best.values(), key=lambda item: float(item["certificate_score"]))


def select_parent(
    rng: np.random.Generator,
    bank: list[dict[str, Any]],
    lane: str,
) -> dict[str, Any] | None:
    if lane == "fresh" or not bank:
        return None
    if lane == "elite_refine":
        return rank_choice(rng, bank[: min(240, len(bank))])
    if lane == "basin_refine":
        champions = basin_champions(bank)
        return champions[int(rng.integers(0, min(len(champions), 600)))]
    if lane == "degree_expand":
        degree_ranked = sorted(
            bank,
            key=lambda item: (
                int(item.get("max_multiplier_degree", 1)),
                float(item["certificate_score"]),
            ),
        )
        return rank_choice(rng, degree_ranked[: min(400, len(degree_ranked))])
    if lane == "support_escape":
        champions = lineage_champions(bank)
        return champions[int(rng.integers(0, min(len(champions), 700)))]
    champions = basin_champions(bank)
    return rank_choice(rng, champions[: min(300, len(champions))])


def lane_parameters(lane: str) -> tuple[float, float, float]:
    return {
        "fresh": (0.0, 0.0, 0.0),
        "elite_refine": (0.06, 0.90, 0.85),
        "basin_refine": (0.18, 0.72, 0.72),
        "degree_expand": (0.10, 0.80, 0.55),
        "support_escape": (0.45, 0.45, 0.45),
        "contrast_focus": (0.035, 0.94, 0.92),
    }[lane]


def stable_bucket(namespace: str, key: str, count: int) -> int:
    payload = f"{namespace}:{key}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") % count


def candidate_meta(result: dict[str, Any], filename: str) -> dict[str, Any]:
    return {
        "candidate_id": str(result["candidate_id"]),
        "score": float(result["certificate_score"]),
        "filename": filename,
        "exact_verified": bool(result.get("exact_verified", False)),
        "basin": str(result.get("basin_fingerprint", "unknown")),
        "lineage": str(result.get("lineage_root", result["candidate_id"])),
    }


def prune_ranked(store: dict[str, dict[str, Any]], limit: int) -> None:
    if len(store) <= limit:
        return
    chosen = sorted(store.values(), key=lambda item: (item["score"], item["candidate_id"]))[:limit]
    store.clear()
    store.update((item["candidate_id"], item) for item in chosen)


def selected_records(
    elites: dict[str, dict[str, Any]],
    exact: dict[str, dict[str, Any]],
    basins: dict[int, dict[str, Any]],
    lineages: dict[int, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for group in (elites.values(), exact.values(), basins.values(), lineages.values()):
        for item in group:
            current = selected.get(item["candidate_id"])
            if current is None or item["score"] < current["score"]:
                selected[item["candidate_id"]] = item
    return selected


def retain_candidate(
    root: Path,
    result: dict[str, Any],
    elites: dict[str, dict[str, Any]],
    exact: dict[str, dict[str, Any]],
    basins: dict[int, dict[str, Any]],
    lineages: dict[int, dict[str, Any]],
) -> int:
    before = selected_records(elites, exact, basins, lineages)
    candidate_id = str(result["candidate_id"])
    filename = f"candidate-{candidate_id}.json.gz"
    item = candidate_meta(result, filename)

    elites[candidate_id] = item
    prune_ranked(elites, ELITE_LIMIT)
    if item["exact_verified"]:
        exact[candidate_id] = item
        prune_ranked(exact, EXACT_LIMIT)

    basin_bucket = stable_bucket("basin", item["basin"], BASIN_BUCKETS)
    previous_basin = basins.get(basin_bucket)
    if previous_basin is None or item["score"] < previous_basin["score"]:
        basins[basin_bucket] = item

    lineage_bucket = stable_bucket("lineage", item["lineage"], LINEAGE_BUCKETS)
    previous_lineage = lineages.get(lineage_bucket)
    if previous_lineage is None or item["score"] < previous_lineage["score"]:
        lineages[lineage_bucket] = item

    after = selected_records(elites, exact, basins, lineages)
    if candidate_id in after:
        candidate_path = root / filename
        with gzip.open(candidate_path, "wt", encoding="utf-8", compresslevel=6) as out:
            json.dump(result, out, sort_keys=True, separators=(",", ":"))
            out.write("\n")

    for removed_id in set(before) - set(after):
        old_path = root / before[removed_id]["filename"]
        if old_path.exists():
            old_path.unlink()

    if len(after) > MAX_RETAINED_PER_WORKER:
        raise RuntimeError("candidate retention invariant exceeded")
    return len(after)


def worker_main(
    repo: str,
    output: str,
    run_index: int,
    job_id: int,
    worker_id: int,
    base_seed: int,
    deadline: float,
    max_attempts: int,
    profile: str,
    weights: dict[str, float],
) -> None:
    repo_path = Path(repo)
    root = Path(output) / f"worker-{worker_id}"
    root.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(
        base_seed + run_index * 10_000_019 + job_id * 100_003 + worker_id * 1_009
    )
    bank, bank_error = load_candidate_bank(repo_path)
    elites: dict[str, dict[str, Any]] = {}
    exact: dict[str, dict[str, Any]] = {}
    basins: dict[int, dict[str, Any]] = {}
    lineages: dict[int, dict[str, Any]] = {}
    attempts = 0
    errors = 0
    exact_count = 0
    retained_count = 0
    lane_counts: Counter[str] = Counter()
    parent_counts: Counter[str] = Counter()
    started = time.time()

    if bank_error:
        append_jsonl(root / "warnings.jsonl", {"warning": "candidate_bank_unreadable", "message": bank_error})

    while time.time() < deadline and (max_attempts <= 0 or attempts < max_attempts):
        attempt_started = time.time()
        try:
            lane = weighted_lane(rng, weights)
            parent = select_parent(rng, bank, lane)
            support_mutation, equation_retention, feature_retention = lane_parameters(lane)
            shape = shape_for(job_id, worker_id, run_index + attempts, profile, lane)
            result = search_once(
                rng,
                shape,
                parent=parent,
                lane=lane,
                support_mutation=support_mutation,
                equation_retention=equation_retention,
                feature_retention=feature_retention,
            )
            candidate_id = f"ta20-r{run_index:03d}-j{job_id:02d}-w{worker_id}-a{attempts:07d}"
            root_id = candidate_id if parent is None else str(parent.get("lineage_root", parent.get("candidate_id", candidate_id)))
            depth = 0 if parent is None else int(parent.get("lineage_depth", 0)) + 1
            result.update(
                {
                    "candidate_id": candidate_id,
                    "run_index": run_index,
                    "job_id": job_id,
                    "worker_id": worker_id,
                    "attempt": attempts,
                    "profile": profile,
                    "lineage_root": root_id,
                    "lineage_depth": depth,
                    "parent_basin_fingerprint": None if parent is None else parent.get("basin_fingerprint"),
                    "improved_parent": (
                        parent is not None
                        and result.get("parent_certificate_score") is not None
                        and float(result["certificate_score"]) < float(result["parent_certificate_score"])
                    ),
                    "elapsed_seconds": time.time() - attempt_started,
                }
            )
            lane_counts[lane] += 1
            if parent is not None:
                parent_counts[str(parent.get("candidate_id", "unknown"))] += 1
            if result.get("exact_verified"):
                exact_count += 1

            append_jsonl(
                root / "metrics.jsonl",
                {
                    "attempt": attempts,
                    "candidate_id": candidate_id,
                    "certificate_score": result["certificate_score"],
                    "coefficient_max": result["coefficient_max"],
                    "lane": lane,
                    "profile": profile,
                    "basin_fingerprint": result["basin_fingerprint"],
                    "lineage_root": root_id,
                    "max_multiplier_degree": result["max_multiplier_degree"],
                    "parent_candidate_id": result["parent_candidate_id"],
                    "improved_parent": result["improved_parent"],
                    "exact_verified": result["exact_verified"],
                    "elapsed_seconds": result["elapsed_seconds"],
                },
            )
            retained_count = retain_candidate(root, result, elites, exact, basins, lineages)
        except BaseException as exc:
            errors += 1
            append_jsonl(
                root / "errors.jsonl",
                {
                    "attempt": attempts,
                    "error": type(exc).__name__,
                    "message": str(exc),
                    "traceback": traceback.format_exc(),
                },
            )

        attempts += 1
        if attempts % 5 == 0 or time.time() >= deadline:
            best_score = min((item["score"] for item in elites.values()), default=None)
            atomic_json(
                root / "checkpoint.json",
                {
                    "worker_id": worker_id,
                    "attempts": attempts,
                    "errors": errors,
                    "exact_candidates": exact_count,
                    "retained_candidate_files": retained_count,
                    "retention_limit": MAX_RETAINED_PER_WORKER,
                    "best_score": best_score,
                    "started_at": started,
                    "updated_at": time.time(),
                    "deadline": deadline,
                    "profile": profile,
                    "lane_counts": dict(lane_counts),
                    "distinct_parents_used": len(parent_counts),
                    "bank_size": len(bank),
                    "bank_load_error": bank_error,
                },
            )

    best_score = min((item["score"] for item in elites.values()), default=None)
    atomic_json(
        root / "complete.json",
        {
            "worker_id": worker_id,
            "attempts": attempts,
            "errors": errors,
            "exact_candidates": exact_count,
            "retained_candidate_files": retained_count,
            "retention_limit": MAX_RETAINED_PER_WORKER,
            "best_score": best_score,
            "started_at": started,
            "finished_at": time.time(),
            "stop_reason": "deadline" if time.time() >= deadline else "attempt_cap",
            "profile": profile,
            "lane_counts": dict(lane_counts),
            "distinct_parents_used": len(parent_counts),
            "bank_size": len(bank),
            "bank_load_error": bank_error,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", type=int, required=True)
    parser.add_argument("--run-index", type=int, required=True)
    parser.add_argument("--base-seed", type=int, required=True)
    parser.add_argument("--seconds", type=int, default=21000)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--max-attempts", type=int, default=0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    launch = json.loads((repo / "third-approach-2.0" / "launch.json").read_text())
    profile = str(launch.get("strategy_profile", "balanced"))
    bank, bank_error = load_candidate_bank(repo)
    weights = normalize_weights(profile, len(bank), launch)

    args.output.mkdir(parents=True, exist_ok=True)
    started = time.time()
    reserve = (
        LONG_RUN_SHUTDOWN_RESERVE_SECONDS
        if args.seconds >= 1800
        else max(10, args.seconds // 5)
    )
    deadline = started + max(20, args.seconds - reserve)
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
                profile,
                weights,
            ),
            daemon=False,
        )
        process.start()
        processes.append(process)

    while time.time() < deadline and any(process.is_alive() for process in processes):
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
    aggregate_lanes: Counter[str] = Counter()
    for worker_id, process in enumerate(processes):
        complete = args.output / f"worker-{worker_id}" / "complete.json"
        checkpoint = args.output / f"worker-{worker_id}" / "checkpoint.json"
        source = complete if complete.exists() else checkpoint
        info = json.loads(source.read_text()) if source.exists() else {}
        info["exitcode"] = process.exitcode
        workers.append(info)
        aggregate_lanes.update(info.get("lane_counts", {}))

    manifest = {
        "schema_version": 2,
        "approach": "third-approach-2.0-multibasin-proof-certificates",
        "run_index": args.run_index,
        "job_id": args.job_id,
        "base_seed": args.base_seed,
        "workers": args.workers,
        "max_attempts_per_worker": args.max_attempts,
        "stopping_policy": "time_only" if args.max_attempts <= 0 else "time_or_attempt_cap",
        "requested_runtime_seconds": args.seconds,
        "shutdown_reserve_seconds": reserve,
        "effective_search_seconds": max(20, args.seconds - reserve),
        "max_retained_candidates_per_worker": MAX_RETAINED_PER_WORKER,
        "hostname": socket.gethostname(),
        "started_at": started,
        "finished_at": time.time(),
        "strategy_profile": profile,
        "lane_weights": weights,
        "lane_counts": dict(aggregate_lanes),
        "candidate_bank_size": len(bank),
        "candidate_bank_load_error": bank_error,
        "worker_manifests": workers,
    }
    atomic_json(args.output / "manifest.json", manifest)
    return 0 if any(worker.get("best_score") is not None for worker in workers) else 2


if __name__ == "__main__":
    raise SystemExit(main())
