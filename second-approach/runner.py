#!/usr/bin/env python3
"""Run four independent dense, counterexample-oriented search workers with checkpoints."""
from __future__ import annotations

import argparse
import gzip
import importlib.util
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

import model


def load_exact_analyser(repo: Path):
    path = repo / "runs" / "2026-07-22-a" / "verify.py"
    spec = importlib.util.spec_from_file_location("second_approach_exact", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import exact analyser from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def jsonable_complex(values: np.ndarray) -> list[list[float]]:
    return [[float(z.real), float(z.imag)] for z in values]


def atomic_json(path: Path, document: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def append_jsonl(path: Path, document: dict) -> None:
    with path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n")
        out.flush()
        os.fsync(out.fileno())


def load_seed_bank(repo: Path) -> list[dict]:
    path = repo / "second-approach" / "candidates" / "seed-bank.json.gz"
    if not path.exists():
        return []
    try:
        with gzip.open(path, "rt", encoding="utf-8") as source:
            document = json.load(source)
        return list(document.get("candidates", []))
    except Exception:
        return []


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
    exact = load_exact_analyser(repo_path)
    seed_candidates = load_seed_bank(repo_path)
    rng = np.random.default_rng(
        base_seed + run_index * 10_000_000 + job_id * 100_000 + worker_id * 1_000
    )
    best: list[tuple[float, str]] = []
    attempt = 0
    started = time.time()
    while time.time() < deadline and attempt < max_attempts:
        seed = int(rng.integers(0, 2**63 - 1))
        local = np.random.default_rng(seed)
        attempt_started = time.time()
        try:
            mask, family, initial_x, parent_id = model.choose_support(
                local, run_index, attempt, seed_candidates=seed_candidates
            )
            term_counts = model.active_terms(mask).sum(axis=1)
            binary_relation_rows = int(sum(
                int(term_counts[row]) == 2 for row in model.MIXED_ROWS
            ))
            if binary_relation_rows == 0:
                obstruction = "unresolved_no_binary_relations"
            elif mask.bit_count() <= 60 and binary_relation_rows <= 24:
                obstruction = str(exact.analyse_support(mask))
            else:
                obstruction = "not_checked_dense"
            known_obstruction = obstruction in {
                "inconsistent_signs", "mixed_monomial", "target_zero"
            }
            if known_obstruction and (attempt % 10) != 0:
                append_jsonl(attempts_path, {
                    "attempt": attempt,
                    "seed": seed,
                    "family": family,
                    "support_size": mask.bit_count(),
                    "support_mask_hex": f"{mask:x}",
                    "closed": True,
                    "exact_obstruction": obstruction,
                    "binary_relation_rows": binary_relation_rows,
                    "parent_candidate_id": parent_id,
                    "skipped_known_obstruction": True,
                    "elapsed_seconds": time.time() - attempt_started,
                })
                attempt += 1
                continue
            result = model.solve_support(
                mask, local, max_nfev=max_nfev, initial_x=initial_x
            )
            candidate_id = f"r{run_index:03d}-j{job_id:02d}-w{worker_id}-a{attempt:06d}"
            summary = {
                "candidate_id": candidate_id,
                "attempt": attempt,
                "seed": seed,
                "family": family,
                "support_size": mask.bit_count(),
                "support_mask_hex": f"{mask:x}",
                "closed": True,
                "exact_obstruction": obstruction,
                "binary_relation_rows": binary_relation_rows,
                "parent_candidate_id": parent_id,
                "skipped_known_obstruction": False,
                "status": result["status"],
                "message": result["message"],
                "nfev": result["nfev"],
                "cost": result["cost"],
                "total_l2": result["total_l2"],
                "max_error": result["max_error"],
                "mixed_l2": result["mixed_l2"],
                "mixed_max": result["mixed_max"],
                "mono_max_error": result["mono_max_error"],
                "mono_amplitudes": jsonable_complex(result["mono_amplitudes"]),
                "weight_max_abs": result["weight_max_abs"],
                "weight_min_abs": result["weight_min_abs"],
                "optimality": result["optimality"],
                "success": result["success"],
                "elapsed_seconds": time.time() - attempt_started,
            }
            append_jsonl(attempts_path, summary)
            score = float(result["max_error"])
            should_promote = len(best) < 5 or score < max(item[0] for item in best)
            if should_promote:
                payload = dict(summary)
                active = np.asarray(result["active"], dtype=np.int16)
                x = np.asarray(result["x"], dtype=np.complex128)
                payload["active_variables"] = [int(v) for v in active]
                payload["active_weights"] = jsonable_complex(x[active])
                candidate_path = root / f"candidate-{candidate_id}.json.gz"
                with gzip.open(candidate_path, "wt", encoding="utf-8") as out:
                    json.dump(payload, out, sort_keys=True, separators=(",", ":"))
                    out.write("\n")
                best.append((score, candidate_path.name))
                best.sort()
                while len(best) > 5:
                    _, old_name = best.pop()
                    old_path = root / old_name
                    if old_path.exists():
                        old_path.unlink()
                atomic_json(root / "best.json", {
                    "worker_id": worker_id,
                    "updated_at": time.time(),
                    "best": [{"max_error": value, "file": name} for value, name in best],
                })
        except BaseException as exc:
            append_jsonl(attempts_path, {
                "attempt": attempt,
                "seed": seed,
                "error": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
                "elapsed_seconds": time.time() - attempt_started,
            })
        attempt += 1
        atomic_json(root / "checkpoint.json", {
            "worker_id": worker_id,
            "attempts": attempt,
            "started_at": started,
            "updated_at": time.time(),
            "deadline": deadline,
        })
    atomic_json(root / "complete.json", {
        "worker_id": worker_id,
        "attempts": attempt,
        "started_at": started,
        "finished_at": time.time(),
    })


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-id", type=int, required=True)
    ap.add_argument("--run-index", type=int, required=True)
    ap.add_argument("--base-seed", type=int, required=True)
    ap.add_argument("--seconds", type=int, default=19800)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max-nfev", type=int, default=300)
    ap.add_argument("--max-attempts", type=int, default=1500)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    repo = Path(__file__).resolve().parents[1]
    start = time.time()
    deadline = start + max(60, args.seconds - 600)
    processes: list[mp.Process] = []
    for worker_id in range(args.workers):
        process = mp.Process(
            target=worker_main,
            args=(
                str(repo), str(args.output), args.run_index, args.job_id,
                worker_id, args.base_seed, deadline, args.max_nfev, args.max_attempts,
            ),
            daemon=False,
        )
        process.start()
        processes.append(process)

    while time.time() < deadline and any(p.is_alive() for p in processes):
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
        info = json.loads(checkpoint.read_text()) if checkpoint.exists() else {}
        info["exitcode"] = process.exitcode
        worker_manifests.append(info)
    manifest = {
        "schema_version": 1,
        "run_index": args.run_index,
        "job_id": args.job_id,
        "base_seed": args.base_seed,
        "workers": args.workers,
        "max_nfev": args.max_nfev,
        "max_attempts_per_worker": args.max_attempts,
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
