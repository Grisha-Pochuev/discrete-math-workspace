#!/usr/bin/env python3
"""Checkpointed four-process driver for the third, proof-oriented approach."""
from __future__ import annotations

import argparse
import gzip
import json
import multiprocessing as mp
import os
from pathlib import Path
import signal
import socket
import time
import traceback

import numpy as np

from certificate import search_once, shape_for


def atomic_json(path: Path, document: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def append_jsonl(path: Path, document: dict) -> None:
    with path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n")
        out.flush()
        os.fsync(out.fileno())


def worker_main(
    output: str,
    run_index: int,
    job_id: int,
    worker_id: int,
    base_seed: int,
    deadline: float,
    max_attempts: int,
) -> None:
    root = Path(output) / f"worker-{worker_id}"
    root.mkdir(parents=True, exist_ok=True)
    metrics_path = root / "metrics.jsonl"
    rng = np.random.default_rng(
        base_seed + run_index * 10_000_019 + job_id * 100_003 + worker_id * 1_009
    )
    shape = shape_for(job_id, worker_id, run_index)
    best: list[tuple[float, str]] = []
    attempt = 0
    errors = 0
    started = time.time()

    while time.time() < deadline and (max_attempts <= 0 or attempt < max_attempts):
        attempt_started = time.time()
        try:
            result = search_once(rng, shape)
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
    start = time.time()
    reserve = 480 if args.seconds >= 1800 else max(10, args.seconds // 5)
    deadline = start + max(20, args.seconds - reserve)
    processes: list[mp.Process] = []
    for worker_id in range(args.workers):
        process = mp.Process(
            target=worker_main,
            args=(
                str(args.output),
                args.run_index,
                args.job_id,
                worker_id,
                args.base_seed,
                deadline,
                args.max_attempts,
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
        info = json.loads(complete.read_text()) if complete.exists() else {}
        info["exitcode"] = process.exitcode
        workers.append(info)

    manifest = {
        "schema_version": 1,
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
        "worker_manifests": workers,
    }
    atomic_json(args.output / "manifest.json", manifest)
    return 0 if any(w.get("best_score") is not None for w in workers) else 2


if __name__ == "__main__":
    raise SystemExit(main())
