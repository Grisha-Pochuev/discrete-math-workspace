#!/usr/bin/env python3
"""Run one four-worker shard of Second approach 2.0."""
from __future__ import annotations

import argparse
import gzip
import json
import multiprocessing as mp
import os
from pathlib import Path
import platform
import signal
import socket
import time
import traceback

import numpy as np

import engine


def atomic_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def append_jsonl(path: Path, document: dict) -> None:
    with path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n")
        out.flush()
        os.fsync(out.fileno())


def complex_pairs(values: np.ndarray) -> list[list[float]]:
    return [[float(z.real), float(z.imag)] for z in values]


def sanitize_initial_x(
    initial_x: np.ndarray | None,
    bound: float,
) -> tuple[np.ndarray | None, int]:
    """Keep inherited starts strictly inside scipy's box constraints.

    Legacy candidates may contain coordinates on the old +/-bound boundary.
    The legacy model adds a small random perturbation before least_squares,
    which can otherwise make x0 infeasible. Keep a generous interior margin.
    """
    if initial_x is None:
        return None, 0
    values = np.asarray(initial_x, dtype=np.complex128).copy()
    margin = max(0.25, 0.05 * float(bound))
    limit = max(0.0, float(bound) - margin)
    clipped_real = np.clip(values.real, -limit, limit)
    clipped_imag = np.clip(values.imag, -limit, limit)
    changed = int(
        np.count_nonzero(clipped_real != values.real)
        + np.count_nonzero(clipped_imag != values.imag)
    )
    return clipped_real + 1j * clipped_imag, changed


def worker_main(
    repo: str,
    output: str,
    run_index: int,
    job_id: int,
    worker_id: int,
    base_seed: int,
    deadline: float,
    max_nfev: int,
    max_attempts: int,
) -> None:
    repo_path = Path(repo)
    root = Path(output) / f"worker-{worker_id}"
    root.mkdir(parents=True, exist_ok=True)
    attempts_path = root / "attempts.jsonl"
    model = engine.load_legacy_model(repo_path)
    exact = engine.load_exact_analyser(repo_path)
    legacy_bank = engine.load_bank(repo_path / "second-approach" / "candidates" / "seed-bank.json.gz")
    new_bank = engine.load_bank(repo_path / "second-approach-2.0" / "candidates" / "bank.json.gz")
    lane = engine.lane_for(job_id, worker_id)
    rng = np.random.default_rng(
        base_seed + run_index * 10_000_019 + job_id * 100_003 + worker_id * 1009
    )
    best: list[tuple[float, str]] = []
    attempt = 0
    errors = 0
    optimized = 0
    skipped = 0
    started = time.time()

    while time.time() < deadline and (max_attempts <= 0 or attempt < max_attempts):
        seed = int(rng.integers(0, 2**63 - 1))
        local = np.random.default_rng(seed)
        attempt_started = time.time()
        error_context: dict = {"lane": lane}
        try:
            selection = engine.choose_support(
                model, exact, local, lane, legacy_bank, new_bank
            )
            mask = int(selection.pop("mask"))
            initial_x = selection.pop("initial_x", None)
            family = str(selection.pop("family"))
            error_context.update(
                {
                    "family": family,
                    "support_size": mask.bit_count(),
                    "support_mask_hex": f"{mask:x}",
                    "parent_candidate_id": selection.get("parent_candidate_id"),
                    "parent_max_error": selection.get("parent_max_error"),
                }
            )
            obstruction, binary_rows = engine.exact_status(model, exact, mask)
            known = obstruction in engine.KNOWN_OBSTRUCTIONS
            should_skip = (
                known
                and lane not in {"obstruction_boundary", "precision_audit"}
                and attempt % 5 != 0
            )
            base_record = {
                "attempt": attempt,
                "seed": seed,
                "lane": lane,
                "family": family,
                "support_size": mask.bit_count(),
                "support_mask_hex": f"{mask:x}",
                "support_fingerprint": engine.support_fingerprint(mask),
                "exact_obstruction": obstruction,
                "binary_relation_rows": binary_rows,
                **selection,
            }
            if should_skip:
                append_jsonl(
                    attempts_path,
                    {
                        **base_record,
                        "skipped_known_obstruction": True,
                        "elapsed_seconds": time.time() - attempt_started,
                    },
                )
                skipped += 1
                attempt += 1
                continue

            solve_nfev = max_nfev
            scale = 0.12
            bound = 8.0
            if lane == "precision_audit":
                solve_nfev = max(900, max_nfev * 3)
                scale = 0.03
                bound = 16.0
            initial_x, clipped_coordinates = sanitize_initial_x(initial_x, bound)
            result = model.solve_support(
                mask,
                local,
                max_nfev=solve_nfev,
                scale=scale,
                bound=bound,
                initial_x=initial_x,
            )
            optimized += 1
            candidate_id = (
                f"sa20-r{run_index:03d}-j{job_id:02d}-w{worker_id}-a{attempt:06d}"
            )
            top_residuals, basin_fingerprint = engine.residual_signature(
                model, np.asarray(result["x"], dtype=np.complex128)
            )
            parent_score = selection.get("parent_max_error")
            improved_parent = bool(
                parent_score is not None
                and float(result["max_error"]) < float(parent_score)
            )
            summary = {
                **base_record,
                "candidate_id": candidate_id,
                "skipped_known_obstruction": False,
                "initial_point_clipped_coordinates": clipped_coordinates,
                "status": result["status"],
                "message": result["message"],
                "nfev": result["nfev"],
                "cost": result["cost"],
                "total_l2": result["total_l2"],
                "max_error": result["max_error"],
                "mixed_l2": result["mixed_l2"],
                "mixed_max": result["mixed_max"],
                "mono_max_error": result["mono_max_error"],
                "mono_amplitudes": complex_pairs(result["mono_amplitudes"]),
                "weight_max_abs": result["weight_max_abs"],
                "weight_min_abs": result["weight_min_abs"],
                "optimality": result["optimality"],
                "numerical_success": result["success"],
                "top_mixed_residuals": top_residuals,
                "residual_basin_fingerprint": basin_fingerprint,
                "improved_parent": improved_parent,
                "elapsed_seconds": time.time() - attempt_started,
            }
            append_jsonl(attempts_path, summary)
            score = float(result["max_error"])
            promote = len(best) < 8 or score < max(item[0] for item in best)
            if promote:
                payload = dict(summary)
                active = np.asarray(result["active"], dtype=np.int16)
                x = np.asarray(result["x"], dtype=np.complex128)
                payload["active_variables"] = [int(v) for v in active]
                payload["active_weights"] = complex_pairs(x[active])
                payload["legacy_rooted"] = bool(
                    payload.get("legacy_rooted", lane == "legacy_control")
                )
                if not payload.get("lineage_root"):
                    payload["lineage_root"] = candidate_id
                candidate_path = root / f"candidate-{candidate_id}.json.gz"
                with gzip.open(
                    candidate_path, "wt", encoding="utf-8", compresslevel=9
                ) as out:
                    json.dump(payload, out, sort_keys=True, separators=(",", ":"))
                    out.write("\n")
                best.append((score, candidate_path.name))
                best.sort()
                while len(best) > 8:
                    _, old_name = best.pop()
                    old_path = root / old_name
                    if old_path.exists():
                        old_path.unlink()
                atomic_json(
                    root / "best.json",
                    {
                        "worker_id": worker_id,
                        "lane": lane,
                        "updated_at": time.time(),
                        "best": [
                            {"max_error": value, "file": name}
                            for value, name in best
                        ],
                    },
                )
        except BaseException as exc:
            errors += 1
            append_jsonl(
                attempts_path,
                {
                    "attempt": attempt,
                    "seed": seed,
                    **error_context,
                    "error": type(exc).__name__,
                    "message": str(exc),
                    "traceback": traceback.format_exc(),
                    "elapsed_seconds": time.time() - attempt_started,
                },
            )
        attempt += 1
        atomic_json(
            root / "checkpoint.json",
            {
                "worker_id": worker_id,
                "global_worker_id": job_id * 4 + worker_id,
                "lane": lane,
                "attempts": attempt,
                "optimized_attempts": optimized,
                "skipped_known_obstruction": skipped,
                "errors": errors,
                "best_score": best[0][0] if best else None,
                "started_at": started,
                "updated_at": time.time(),
                "deadline": deadline,
            },
        )

    atomic_json(
        root / "complete.json",
        {
            "worker_id": worker_id,
            "global_worker_id": job_id * 4 + worker_id,
            "lane": lane,
            "attempts": attempt,
            "optimized_attempts": optimized,
            "skipped_known_obstruction": skipped,
            "errors": errors,
            "best_score": best[0][0] if best else None,
            "started_at": started,
            "finished_at": time.time(),
            "stop_reason": "deadline" if time.time() >= deadline else "attempt_cap",
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", type=int, required=True)
    parser.add_argument("--run-index", type=int, required=True)
    parser.add_argument("--base-seed", type=int, required=True)
    parser.add_argument("--seconds", type=int, default=21000)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--max-nfev", type=int, default=300)
    parser.add_argument("--max-attempts", type=int, default=0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.workers != 4 and args.max_attempts == 0:
        raise ValueError("long runs require exactly four workers per job")
    args.output.mkdir(parents=True, exist_ok=True)
    repo = Path(__file__).resolve().parents[1]
    start = time.time()
    deadline = start + max(60, args.seconds - 600)
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
                args.max_nfev,
                args.max_attempts,
            ),
            daemon=False,
        )
        process.start()
        processes.append(process)

    while time.time() < deadline and any(
        process.is_alive() for process in processes
    ):
        time.sleep(5)
    for process in processes:
        if process.is_alive():
            process.terminate()
    for process in processes:
        process.join(timeout=30)
        if process.is_alive():
            os.kill(process.pid, signal.SIGKILL)
            process.join(timeout=5)

    worker_manifests = []
    for worker_id, process in enumerate(processes):
        checkpoint = args.output / f"worker-{worker_id}" / "checkpoint.json"
        complete = args.output / f"worker-{worker_id}" / "complete.json"
        source = complete if complete.exists() else checkpoint
        info = (
            json.loads(source.read_text(encoding="utf-8"))
            if source.exists()
            else {
                "worker_id": worker_id,
                "lane": engine.lane_for(args.job_id, worker_id),
                "missing_checkpoint": True,
            }
        )
        info["exitcode"] = process.exitcode
        worker_manifests.append(info)

    manifest = {
        "schema_version": 1,
        "approach": "second-approach-2.0-independent-basin-counterexample-search",
        "run_index": args.run_index,
        "job_id": args.job_id,
        "base_seed": args.base_seed,
        "workers": args.workers,
        "lane_assignments": [
            engine.lane_for(args.job_id, worker_id)
            for worker_id in range(args.workers)
        ],
        "max_nfev": args.max_nfev,
        "max_attempts_per_worker": args.max_attempts,
        "stopping_policy": (
            "time_only" if args.max_attempts <= 0 else "time_or_attempt_cap"
        ),
        "requested_seconds": args.seconds,
        "started_at": start,
        "finished_at": time.time(),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "worker_manifests": worker_manifests,
    }
    atomic_json(args.output / "manifest.json", manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
