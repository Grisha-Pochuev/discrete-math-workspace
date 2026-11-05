#!/usr/bin/env python3
"""Aggregate one GitHub Actions second-approach run into a deterministic repo archive."""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
import os
from pathlib import Path
import time


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as source:
        for line in source:
            if line.strip():
                yield json.loads(line)


def load_gzip_json(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as source:
        return json.load(source)


def atomic_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", type=Path, required=True)
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--run-id", type=int, required=True)
    ap.add_argument("--run-index", type=int, required=True)
    ap.add_argument("--conclusion", required=True)
    ap.add_argument("--expected-jobs", type=int, default=20)
    ap.add_argument("--min-jobs", type=int, default=16)
    args = ap.parse_args()

    root = args.repo / "second-approach"
    output = root / "runs" / f"run-{args.run_index:03d}-{args.run_id}"
    if output.exists():
        print(f"archive already exists: {output}")
        return 0
    output.mkdir(parents=True)
    promoted_dir = output / "promoted"
    promoted_dir.mkdir()

    manifests = []
    attempts = []
    candidate_payloads = []
    raw_candidate_files = sorted(args.artifacts.rglob("candidate-*.json.gz"))
    for path in sorted(args.artifacts.rglob("manifest.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if "job_id" in document and "run_index" in document:
            document["_source"] = path.relative_to(args.artifacts).as_posix()
            manifests.append(document)
    for path in sorted(args.artifacts.rglob("attempts.jsonl")):
        source_label = path.relative_to(args.artifacts).as_posix()
        for record in read_jsonl(path):
            record["_source"] = source_label
            attempts.append(record)
    for path in raw_candidate_files:
        try:
            payload = load_gzip_json(path)
            payload["_source"] = path.relative_to(args.artifacts).as_posix()
            candidate_payloads.append(payload)
        except Exception as exc:
            attempts.append({
                "error": "candidate_read_error",
                "message": str(exc),
                "_source": path.relative_to(args.artifacts).as_posix(),
            })

    job_ids = sorted({int(item["job_id"]) for item in manifests})
    missing_jobs = sorted(set(range(args.expected_jobs)) - set(job_ids))
    optimized = [item for item in attempts if "max_error" in item]
    failures = [item for item in attempts if "error" in item]
    skipped = [item for item in attempts if item.get("skipped_known_obstruction")]
    successes = [item for item in optimized if item.get("success")]
    best = sorted(
        optimized,
        key=lambda item: (float(item["max_error"]), float(item.get("total_l2", 1e300))),
    )
    candidate_payloads.sort(
        key=lambda item: (
            float(item.get("max_error", 1e300)),
            float(item.get("total_l2", 1e300)),
        )
    )

    family_counts = Counter(str(item.get("family", "unknown")) for item in attempts)
    obstruction_counts = Counter(
        str(item.get("exact_obstruction", "unknown")) for item in attempts
    )
    support_size_counts = Counter(
        int(item["support_size"]) for item in attempts if "support_size" in item
    )

    accepted = len(job_ids) >= args.min_jobs and len(optimized) > 0
    summary = {
        "schema_version": 1,
        "run_id": args.run_id,
        "run_index": args.run_index,
        "workflow_conclusion": args.conclusion,
        "accepted": accepted,
        "minimum_jobs_for_acceptance": args.min_jobs,
        "jobs_expected": args.expected_jobs,
        "jobs_present": job_ids,
        "jobs_missing": missing_jobs,
        "manifests": len(manifests),
        "attempts_total": len(attempts),
        "optimized_attempts": len(optimized),
        "skipped_known_obstruction": len(skipped),
        "worker_errors": len(failures),
        "numerical_successes": len(successes),
        "families": dict(sorted(family_counts.items())),
        "exact_obstruction_statuses": dict(sorted(obstruction_counts.items())),
        "support_sizes": {str(k): v for k, v in sorted(support_size_counts.items())},
        "best": best[:20],
        "created_at_unix": time.time(),
    }
    atomic_json(output / "job-manifests.json", {"manifests": manifests})

    attempts_dir = output / "attempts"
    attempts_dir.mkdir()
    attempt_parts = []
    chunk_size = 25_000
    for part_index, start in enumerate(range(0, len(attempts), chunk_size)):
        part = attempts[start : start + chunk_size]
        part_path = attempts_dir / f"part-{part_index:04d}.jsonl.gz"
        with gzip.open(part_path, "wt", encoding="utf-8", compresslevel=9) as out:
            for item in part:
                out.write(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n")
        attempt_parts.append({
            "file": part_path.relative_to(output).as_posix(),
            "records": len(part),
        })
    if not attempt_parts:
        part_path = attempts_dir / "part-0000.jsonl.gz"
        with gzip.open(part_path, "wt", encoding="utf-8", compresslevel=9):
            pass
        attempt_parts.append({
            "file": part_path.relative_to(output).as_posix(),
            "records": 0,
        })
    summary["attempt_parts"] = attempt_parts
    atomic_json(output / "summary.json", summary)

    copied_names = set()
    for index, payload in enumerate(candidate_payloads):
        candidate_id = str(payload.get("candidate_id", f"candidate-{index:04d}"))
        name = f"{index:04d}-{candidate_id}.json.gz"
        if name in copied_names:
            continue
        copied_names.add(name)
        payload.pop("_source", None)
        with gzip.open(promoted_dir / name, "wt", encoding="utf-8", compresslevel=9) as out:
            json.dump(payload, out, sort_keys=True, separators=(",", ":"))
            out.write("\n")

    best_error = float(best[0]["max_error"]) if best else None
    readme = [
        f"# Second-approach run {args.run_index:03d}",
        "",
        f"- GitHub Actions run: `{args.run_id}`",
        f"- workflow conclusion: `{args.conclusion}`",
        f"- accepted as a completed research run: `{accepted}`",
        f"- jobs present: {len(job_ids)}/{args.expected_jobs}",
        f"- optimized attempts: {len(optimized)}",
        f"- skipped controls with known sparse obstruction: {len(skipped)}",
        f"- numerical solutions below 1e-8: {len(successes)}",
        f"- best maximum equation error: {best_error!r}",
        f"- preserved full-weight candidates: {len(candidate_payloads)}",
        "",
        "A failed workflow conclusion does not invalidate completed worker checkpoints. Missing jobs and worker errors are recorded explicitly in `summary.json`.",
        "",
        "This is numerical counterexample-search evidence, not a proof. Promising candidates require independent high-precision and exact verification.",
    ]
    (output / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")

    prior = []
    seed_path = root / "candidates" / "seed-bank.json.gz"
    if seed_path.exists():
        try:
            prior = list(load_gzip_json(seed_path).get("candidates", []))
        except Exception:
            prior = []
    merged = prior + candidate_payloads
    by_id = {}
    for item in merged:
        candidate_id = str(item.get("candidate_id", ""))
        if candidate_id:
            by_id[candidate_id] = item
    seeds = sorted(
        by_id.values(), key=lambda item: float(item.get("max_error", 1e300))
    )[:100]
    seed_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(seed_path, "wt", encoding="utf-8", compresslevel=9) as out:
        json.dump(
            {"schema_version": 1, "candidates": seeds},
            out,
            sort_keys=True,
            separators=(",", ":"),
        )
        out.write("\n")

    state_path = root / "control.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if accepted:
        state["completed_runs"] = max(
            int(state.get("completed_runs", 0)), args.run_index + 1
        )
        state["next_run_index"] = args.run_index + 1
        state["next_seed"] = (
            int(state.get("base_seed", 20260726))
            + (args.run_index + 1) * 1_000_003
        )
    else:
        state["next_run_index"] = args.run_index
        state["next_seed"] = int(
            state.get("next_seed", state.get("base_seed", 20260726))
        ) + 97
    state["last_run_id"] = args.run_id
    state["last_run_index"] = args.run_index
    state["last_conclusion"] = args.conclusion
    state["last_run_accepted"] = accepted
    atomic_json(state_path, state)

    checksum_files = sorted(
        path
        for path in output.rglob("*")
        if path.is_file() and path.name != "checksums.sha256"
    )
    with (output / "checksums.sha256").open("w", encoding="utf-8") as out:
        for path in checksum_files:
            out.write(f"{sha256(path)}  {path.relative_to(output).as_posix()}\n")

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
