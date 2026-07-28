#!/usr/bin/env python3
"""Aggregate one third-approach matrix run into a compact committed archive."""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import statistics
import time


def read_gzip_json(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as source:
        return json.load(source)


def write_gzip_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as out:
        json.dump(document, out, sort_keys=True, separators=(",", ":"))
        out.write("\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", type=Path, required=True)
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--run-id", type=int, required=True)
    ap.add_argument("--expected-jobs", type=int, default=20)
    ap.add_argument("--min-jobs", type=int, default=16)
    args = ap.parse_args()

    launch = json.loads((args.repo / "third-approach" / "launch.json").read_text())
    control_path = args.repo / "third-approach" / "control.json"
    control = json.loads(control_path.read_text())
    run_index = int(launch["run_index"])

    manifests = []
    for path in args.artifacts.rglob("manifest.json"):
        try:
            item = json.loads(path.read_text())
        except Exception:
            continue
        if int(item.get("run_index", -1)) == run_index:
            manifests.append(item)

    candidates = []
    for path in args.artifacts.rglob("candidate-*.json.gz"):
        try:
            item = read_gzip_json(path)
        except Exception:
            continue
        if int(item.get("run_index", -1)) == run_index:
            candidates.append(item)
    candidates.sort(key=lambda item: float(item["certificate_score"]))

    completed_jobs = len({int(item["job_id"]) for item in manifests})
    accepted = completed_jobs >= args.min_jobs and bool(candidates)
    run_dir = (
        args.repo
        / "third-approach"
        / "runs"
        / f"run-{run_index:03d}-{args.run_id}"
    )
    run_dir.mkdir(parents=True, exist_ok=True)

    attempts = sum(
        int(worker.get("attempts", 0))
        for manifest in manifests
        for worker in manifest.get("worker_manifests", [])
    )
    errors = sum(
        int(worker.get("errors", 0))
        for manifest in manifests
        for worker in manifest.get("worker_manifests", [])
    )
    scores = [float(item["certificate_score"]) for item in candidates]
    summary = {
        "schema_version": 1,
        "approach": "third-proof-oriented-numerical-certificates",
        "run_id": args.run_id,
        "run_index": run_index,
        "base_seed": int(launch["base_seed"]),
        "accepted": accepted,
        "expected_jobs": args.expected_jobs,
        "minimum_jobs": args.min_jobs,
        "completed_jobs": completed_jobs,
        "attempts": attempts,
        "worker_errors": errors,
        "candidate_count": len(candidates),
        "best_certificate_score": scores[0] if scores else None,
        "median_saved_score": statistics.median(scores) if scores else None,
        "scope": "n=6,d=3 restricted support families",
        "interpretation": (
            "Numerical candidates only. An exact symbolic identity or rational "
            "reconstruction is required before any candidate can count as a proof."
        ),
        "created_at": time.time(),
    }
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_gzip_json(
        run_dir / "top-candidates.json.gz", {"candidates": candidates[:400]}
    )
    write_gzip_json(run_dir / "job-manifests.json.gz", {"manifests": manifests})
    (run_dir / "README.md").write_text(
        "# Third-approach run\n\n"
        f"- GitHub run: `{args.run_id}`\n"
        f"- Research index: `{run_index}`\n"
        f"- Accepted: `{accepted}` ({completed_jobs}/{args.expected_jobs} jobs)\n"
        f"- Attempts: `{attempts}`\n"
        f"- Saved numerical certificate candidates: `{len(candidates)}`\n"
        f"- Best validation score: `{summary['best_certificate_score']}`\n\n"
        "These are proof-oriented numerical leads, not proofs. A candidate becomes "
        "mathematically meaningful only after exact reconstruction and symbolic "
        "verification.\n",
        encoding="utf-8",
    )

    bank_path = args.repo / "third-approach" / "candidates" / "bank.json.gz"
    previous = []
    if bank_path.exists():
        try:
            previous = list(read_gzip_json(bank_path).get("candidates", []))
        except Exception:
            previous = []
    merged = {
        str(item["candidate_id"]): item for item in previous + candidates[:400]
    }
    bank = sorted(
        merged.values(), key=lambda item: float(item["certificate_score"])
    )[:800]
    write_gzip_json(
        bank_path, {"updated_from_run_id": args.run_id, "candidates": bank}
    )

    if accepted and int(control.get("last_run_id") or 0) != args.run_id:
        control.update(
            {
                "completed_runs": int(control.get("completed_runs", 0)) + 1,
                "last_run_id": args.run_id,
                "last_run_index": run_index,
                "last_run_accepted": True,
                "next_run_index": run_index + 1,
                "next_seed": int(launch["base_seed"]) + 1_000_003,
            }
        )
    elif not accepted:
        control["last_run_accepted"] = False
    control_path.write_text(
        json.dumps(control, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
