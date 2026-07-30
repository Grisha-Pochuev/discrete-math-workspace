#!/usr/bin/env python3
"""Aggregate one Second approach 2.0 workflow run into a deterministic archive."""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
import os
from pathlib import Path
import statistics
import time
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as source:
        for line in source:
            if line.strip():
                yield json.loads(line)


def load_gzip_json(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as source:
        return json.load(source)


def atomic_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def score(item: dict[str, Any]) -> tuple[float, float]:
    return float(item.get("max_error", 1e300)), float(item.get("total_l2", 1e300))


def is_independent(item: dict[str, Any]) -> bool:
    lane = str(item.get("lane", ""))
    return lane in {"fresh_independent", "obstruction_boundary", "novelty_far"} and not bool(item.get("legacy_rooted", False))


def select_bank(candidates: list[dict[str, Any]], limit: int = 1200) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for item in candidates:
        candidate_id = str(item.get("candidate_id", ""))
        if candidate_id:
            by_id[candidate_id] = item
    ranked = sorted(by_id.values(), key=score)
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    support_counts: Counter[str] = Counter()
    basin_counts: Counter[str] = Counter()
    lane_counts: Counter[str] = Counter()

    def add(item: dict[str, Any], *, support_cap: int = 3, basin_cap: int = 25, lane_cap: int | None = None) -> bool:
        candidate_id = str(item.get("candidate_id", ""))
        if not candidate_id or candidate_id in selected_ids:
            return False
        lane = str(item.get("lane", "unknown"))
        support = str(item.get("support_fingerprint", item.get("support_mask_hex", "unknown")))
        basin = str(item.get("residual_basin_fingerprint", "unknown"))
        if support_counts[support] >= support_cap or basin_counts[basin] >= basin_cap:
            return False
        if lane_cap is not None and lane_counts[lane] >= lane_cap:
            return False
        selected.append(item)
        selected_ids.add(candidate_id)
        support_counts[support] += 1
        basin_counts[basin] += 1
        lane_counts[lane] += 1
        return True

    for item in ranked:
        if is_independent(item):
            add(item, support_cap=2, basin_cap=20, lane_cap=700)
        if len(selected) >= 600:
            break

    for lane, quota in {
        "fresh_independent": 180,
        "obstruction_boundary": 180,
        "novelty_far": 180,
        "legacy_control": 100,
        "precision_audit": 180,
    }.items():
        for item in ranked:
            if str(item.get("lane", "")) == lane:
                add(item, support_cap=3, basin_cap=25, lane_cap=quota)
            if lane_counts[lane] >= quota or len(selected) >= limit:
                break

    for item in ranked:
        add(item, support_cap=4, basin_cap=35)
        if len(selected) >= limit:
            break
    return selected[:limit]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--conclusion", required=True)
    parser.add_argument("--expected-jobs", type=int, default=20)
    parser.add_argument("--min-jobs", type=int, default=16)
    args = parser.parse_args()

    root = args.repo / "second-approach-2.0"
    manifests: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    payloads: list[dict[str, Any]] = []

    for path in sorted(args.artifacts.rglob("manifest.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            if document.get("approach") == "second-approach-2.0-independent-basin-counterexample-search":
                document["_source"] = path.relative_to(args.artifacts).as_posix()
                manifests.append(document)
        except Exception:
            continue
    if not manifests:
        raise RuntimeError("no readable Second approach 2.0 manifests found")
    run_indexes = {int(item["run_index"]) for item in manifests}
    base_seeds = {int(item["base_seed"]) for item in manifests}
    if len(run_indexes) != 1 or len(base_seeds) != 1:
        raise RuntimeError(f"mixed run configuration in artifacts: indexes={run_indexes}, seeds={base_seeds}")
    run_index = next(iter(run_indexes))
    base_seed = next(iter(base_seeds))
    output = root / "runs" / f"run-{run_index:03d}-{args.run_id}"
    if output.exists():
        print(f"archive already exists: {output}")
        return 0
    output.mkdir(parents=True)
    promoted_dir = output / "promoted"
    promoted_dir.mkdir()

    for path in sorted(args.artifacts.rglob("attempts.jsonl")):
        source_label = path.relative_to(args.artifacts).as_posix()
        try:
            for record in read_jsonl(path):
                record["_source"] = source_label
                attempts.append(record)
        except Exception as exc:
            attempts.append({"error": "attempt_log_read_error", "message": str(exc), "_source": source_label})
    for path in sorted(args.artifacts.rglob("candidate-*.json.gz")):
        try:
            payload = load_gzip_json(path)
            payload["_source"] = path.relative_to(args.artifacts).as_posix()
            payloads.append(payload)
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
    numerical_successes = [item for item in optimized if item.get("numerical_success")]
    optimized.sort(key=score)
    payloads.sort(key=score)
    accepted = len(job_ids) >= args.min_jobs and len(payloads) > 0 and len(optimized) > 0

    lane_attempt_counts = Counter(str(item.get("lane", "unknown")) for item in attempts)
    lane_optimized_counts = Counter(str(item.get("lane", "unknown")) for item in optimized)
    lane_promoted_counts = Counter(str(item.get("lane", "unknown")) for item in payloads)
    family_counts = Counter(str(item.get("family", "unknown")) for item in attempts)
    obstruction_counts = Counter(str(item.get("exact_obstruction", "unknown")) for item in attempts)
    support_fingerprints = {str(item.get("support_fingerprint")) for item in payloads if item.get("support_fingerprint")}
    basin_fingerprints = {str(item.get("residual_basin_fingerprint")) for item in payloads if item.get("residual_basin_fingerprint")}
    lineage_roots = {str(item.get("lineage_root")) for item in payloads if item.get("lineage_root")}
    old_rooted = [item for item in payloads if bool(item.get("legacy_rooted", False))]
    independent_payloads = [item for item in payloads if is_independent(item)]
    parent_based = [item for item in payloads if item.get("parent_candidate_id")]
    parent_improvements = [item for item in parent_based if item.get("improved_parent")]

    lane_best: dict[str, float] = {}
    for item in optimized:
        lane = str(item.get("lane", "unknown"))
        lane_best[lane] = min(lane_best.get(lane, 1e300), float(item["max_error"]))

    top_row_counts: Counter[str] = Counter()
    for item in independent_payloads[:200]:
        rows = tuple(int(row["row"]) for row in item.get("top_mixed_residuals", [])[:6])
        if rows:
            top_row_counts[",".join(map(str, rows))] += 1

    summary = {
        "schema_version": 1,
        "approach": "second-approach-2.0-independent-basin-counterexample-search",
        "run_id": args.run_id,
        "run_index": run_index,
        "base_seed": base_seed,
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
        "numerical_successes_below_1e-8": len(numerical_successes),
        "promoted_candidates": len(payloads),
        "best_max_error": float(optimized[0]["max_error"]),
        "median_promoted_max_error": float(statistics.median(float(item["max_error"]) for item in payloads)),
        "best_independent_max_error": float(independent_payloads[0]["max_error"]) if independent_payloads else None,
        "best_independent_candidate_id": str(independent_payloads[0].get("candidate_id")) if independent_payloads else None,
        "best_candidate_id": str(optimized[0].get("candidate_id")),
        "lane_attempt_counts": dict(sorted(lane_attempt_counts.items())),
        "lane_optimized_counts": dict(sorted(lane_optimized_counts.items())),
        "lane_promoted_counts": dict(sorted(lane_promoted_counts.items())),
        "lane_best_max_error": dict(sorted(lane_best.items())),
        "families": dict(sorted(family_counts.items())),
        "exact_obstruction_statuses": dict(sorted(obstruction_counts.items())),
        "distinct_support_fingerprints": len(support_fingerprints),
        "distinct_residual_basin_fingerprints": len(basin_fingerprints),
        "distinct_lineage_roots": len(lineage_roots),
        "legacy_rooted_promoted": len(old_rooted),
        "legacy_rooted_promoted_fraction": len(old_rooted) / len(payloads) if payloads else 0.0,
        "independent_promoted": len(independent_payloads),
        "parent_based_promoted": len(parent_based),
        "parent_based_improvements_promoted": len(parent_improvements),
        "repeated_independent_top_residual_signatures": [
            {"rows": key, "count": count} for key, count in top_row_counts.most_common(20)
        ],
        "best": optimized[:30],
        "created_at_unix": time.time(),
        "interpretation": "Floating-point counterexample candidates only; exact verification is required.",
    }

    atomic_json(output / "job-manifests.json", {"manifests": manifests})
    attempts_dir = output / "attempts"
    attempts_dir.mkdir()
    parts = []
    for part_index, start in enumerate(range(0, len(attempts), 25000)):
        part = attempts[start : start + 25000]
        part_path = attempts_dir / f"part-{part_index:04d}.jsonl.gz"
        with gzip.open(part_path, "wt", encoding="utf-8", compresslevel=9) as out:
            for item in part:
                out.write(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n")
        parts.append({"file": part_path.relative_to(output).as_posix(), "records": len(part)})
    if not parts:
        part_path = attempts_dir / "part-0000.jsonl.gz"
        with gzip.open(part_path, "wt", encoding="utf-8", compresslevel=9):
            pass
        parts.append({"file": part_path.relative_to(output).as_posix(), "records": 0})
    summary["attempt_parts"] = parts
    atomic_json(output / "summary.json", summary)

    for index, payload in enumerate(payloads):
        clean = dict(payload)
        clean.pop("_source", None)
        candidate_id = str(clean.get("candidate_id", f"candidate-{index:04d}"))
        with gzip.open(promoted_dir / f"{index:04d}-{candidate_id}.json.gz", "wt", encoding="utf-8", compresslevel=9) as out:
            json.dump(clean, out, sort_keys=True, separators=(",", ":"))
            out.write("\n")

    prior = []
    bank_path = root / "candidates" / "bank.json.gz"
    if bank_path.exists():
        try:
            prior = list(load_gzip_json(bank_path).get("candidates", []))
        except Exception:
            prior = []
    bank = select_bank(prior + payloads, limit=1200)
    bank_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(bank_path, "wt", encoding="utf-8", compresslevel=9) as out:
        json.dump({"schema_version": 1, "candidates": bank}, out, sort_keys=True, separators=(",", ":"))
        out.write("\n")

    state_path = root / "control.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if accepted:
        state["completed_runs"] = max(int(state.get("completed_runs", 0)), run_index + 1)
        state["next_run_index"] = run_index + 1
        state["next_seed"] = int(state.get("base_seed", 20260730)) + (run_index + 1) * 1_000_003
        history = list(state.get("best_score_history", []))
        history.append({
            "run_id": args.run_id,
            "run_index": run_index,
            "best_max_error": summary["best_max_error"],
            "best_independent_max_error": summary["best_independent_max_error"],
            "distinct_support_fingerprints": summary["distinct_support_fingerprints"],
            "distinct_residual_basin_fingerprints": summary["distinct_residual_basin_fingerprints"],
            "legacy_rooted_promoted_fraction": summary["legacy_rooted_promoted_fraction"],
            "lane_best_max_error": summary["lane_best_max_error"],
        })
        state["best_score_history"] = history[-50:]
        current_global = state.get("global_best_max_error")
        if current_global is None or summary["best_max_error"] < float(current_global):
            state["global_best_max_error"] = summary["best_max_error"]
            state["global_best_candidate_id"] = summary["best_candidate_id"]
        current_independent = state.get("global_best_independent_max_error")
        if summary["best_independent_max_error"] is not None and (
            current_independent is None or summary["best_independent_max_error"] < float(current_independent)
        ):
            state["global_best_independent_max_error"] = summary["best_independent_max_error"]
            state["global_best_independent_candidate_id"] = summary["best_independent_candidate_id"]
    else:
        state["next_run_index"] = run_index
        state["next_seed"] = int(state.get("next_seed", base_seed)) + 97
    state["last_run_id"] = args.run_id
    state["last_run_index"] = run_index
    state["last_conclusion"] = args.conclusion
    state["last_run_accepted"] = accepted
    state["candidate_bank_size"] = len(bank)
    atomic_json(state_path, state)

    readme = [
        f"# Second approach 2.0 run {run_index:03d}",
        "",
        f"- GitHub Actions run: `{args.run_id}`",
        f"- accepted: `{accepted}`",
        f"- jobs present: {len(job_ids)}/{args.expected_jobs}",
        f"- total attempts: {len(attempts)}",
        f"- optimized attempts: {len(optimized)}",
        f"- promoted candidates: {len(payloads)}",
        f"- best maximum equation error: {summary['best_max_error']!r}",
        f"- best independent maximum equation error: {summary['best_independent_max_error']!r}",
        f"- distinct support fingerprints: {summary['distinct_support_fingerprints']}",
        f"- distinct residual-basin fingerprints: {summary['distinct_residual_basin_fingerprints']}",
        f"- worker errors: {len(failures)}",
        "",
        "This archive is numerical evidence only, not a counterexample. See `summary.json` for lane comparisons and repeated residual signatures.",
    ]
    (output / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")

    checksum_files = sorted(path for path in output.rglob("*") if path.is_file() and path.name != "checksums.sha256")
    with (output / "checksums.sha256").open("w", encoding="utf-8") as out:
        for path in checksum_files:
            out.write(f"{sha256(path)}  {path.relative_to(output).as_posix()}\n")

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
