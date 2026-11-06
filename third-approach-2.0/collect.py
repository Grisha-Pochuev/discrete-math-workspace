#!/usr/bin/env python3
"""Collect a Third approach 2.0 matrix run and maintain a multi-basin bank."""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import statistics
import time
from typing import Any

PROFILE_ROTATION = ["balanced", "multi_basin", "degree_expand", "support_escape", "contrast_focus"]


def read_gzip_json(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as source:
        return json.load(source)


def write_gzip_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as out:
        json.dump(document, out, sort_keys=True, separators=(",", ":"))
        out.write("\n")


def candidate_key(item: dict[str, Any]) -> str:
    return str(item.get("candidate_id", ""))


def score(item: dict[str, Any]) -> float:
    return float(item["certificate_score"])


def best_per_key(candidates: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for item in candidates:
        key = str(item.get(field, "unknown"))
        if key not in best or score(item) < score(best[key]):
            best[key] = item
    return sorted(best.values(), key=score)


def build_multibasin_bank(
    previous: list[dict[str, Any]],
    current: list[dict[str, Any]],
    *,
    limit: int = 1200,
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for item in previous + current:
        key = candidate_key(item)
        if not key:
            continue
        if key not in merged or score(item) < score(merged[key]):
            merged[key] = item
    ranked = sorted(merged.values(), key=score)
    chosen: list[dict[str, Any]] = []
    chosen_ids: set[str] = set()

    def add(item: dict[str, Any]) -> None:
        key = candidate_key(item)
        if key and key not in chosen_ids and len(chosen) < limit:
            chosen.append(item)
            chosen_ids.add(key)

    for item in ranked[:300]:
        add(item)
    for item in best_per_key(ranked, "lineage_root"):
        add(item)
        if len(chosen) >= 650:
            break
    for item in best_per_key(ranked, "basin_fingerprint"):
        add(item)
        if len(chosen) >= 950:
            break

    current_basins = Counter(str(item.get("basin_fingerprint", "unknown")) for item in chosen)
    current_lineages = Counter(str(item.get("lineage_root", "unknown")) for item in chosen)
    for item in sorted(current, key=score):
        basin = str(item.get("basin_fingerprint", "unknown"))
        lineage = str(item.get("lineage_root", "unknown"))
        if current_basins[basin] >= 3 or current_lineages[lineage] >= 3:
            continue
        before = len(chosen)
        add(item)
        if len(chosen) > before:
            current_basins[basin] += 1
            current_lineages[lineage] += 1
        if len(chosen) >= 1100:
            break
    for item in ranked:
        add(item)
        if len(chosen) >= limit:
            break
    return sorted(chosen, key=score)


def rotate_profile(profile: str) -> str:
    try:
        index = PROFILE_ROTATION.index(profile)
    except ValueError:
        index = 0
    return PROFILE_ROTATION[(index + 1) % len(PROFILE_ROTATION)]


def three_run_gain(history: list[dict[str, Any]]) -> float | None:
    values = [float(item["global_best_certificate_score"]) for item in history if item.get("global_best_certificate_score") is not None]
    if len(values) < 3 or values[-3] <= 0:
        return None
    return (values[-3] - values[-1]) / values[-3]


def contrast_pairs(candidates: list[dict[str, Any]], limit: int = 300) -> list[dict[str, Any]]:
    pairs = []
    for item in candidates:
        parent_id = item.get("parent_candidate_id")
        parent_score = item.get("parent_certificate_score")
        if parent_id is None or parent_score is None:
            continue
        improvement = (float(parent_score) - score(item)) / max(abs(float(parent_score)), 1e-300)
        pairs.append(
            {
                "parent_candidate_id": parent_id,
                "child_candidate_id": item.get("candidate_id"),
                "lineage_root": item.get("lineage_root"),
                "lane": item.get("lane"),
                "parent_score": float(parent_score),
                "child_score": score(item),
                "relative_improvement": improvement,
                "support_distance": item.get("support_distance_from_parent"),
                "inherited_equation_count": item.get("inherited_equation_count"),
                "inherited_feature_count": item.get("inherited_feature_count"),
                "parent_basin": item.get("parent_basin_fingerprint"),
                "child_basin": item.get("basin_fingerprint"),
                "max_multiplier_degree": item.get("max_multiplier_degree"),
            }
        )
    pairs.sort(key=lambda item: (-abs(float(item["relative_improvement"])), float(item["child_score"])))
    return pairs[:limit]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--expected-jobs", type=int, default=20)
    parser.add_argument("--min-jobs", type=int, default=16)
    args = parser.parse_args()

    root = args.repo / "third-approach-2.0"
    launch = json.loads((root / "launch.json").read_text())
    control_path = root / "control.json"
    control = json.loads(control_path.read_text())
    run_index = int(launch["run_index"])
    profile = str(launch.get("strategy_profile", "balanced"))

    manifests = []
    for path in args.artifacts.rglob("manifest.json"):
        try:
            item = json.loads(path.read_text())
        except Exception:
            continue
        if int(item.get("run_index", -1)) == run_index and item.get("approach") == "third-approach-2.0-multibasin-proof-certificates":
            manifests.append(item)

    candidates = []
    for path in args.artifacts.rglob("candidate-*.json.gz"):
        try:
            item = read_gzip_json(path)
        except Exception:
            continue
        if int(item.get("run_index", -1)) == run_index:
            candidates.append(item)
    candidates.sort(key=score)

    completed_jobs = len({int(item["job_id"]) for item in manifests})
    attempts = sum(int(worker.get("attempts", 0)) for manifest in manifests for worker in manifest.get("worker_manifests", []))
    errors = sum(int(worker.get("errors", 0)) for manifest in manifests for worker in manifest.get("worker_manifests", []))
    error_fraction = errors / max(1, attempts)
    accepted = completed_jobs >= args.min_jobs and bool(candidates) and error_fraction <= 0.05

    lane_counts: Counter[str] = Counter()
    for manifest in manifests:
        lane_counts.update(manifest.get("lane_counts", {}))
    scores = [score(item) for item in candidates]
    parent_based = [item for item in candidates if item.get("parent_candidate_id") is not None]
    improved = [item for item in parent_based if item.get("improved_parent")]
    exact = [item for item in candidates if item.get("exact_verified")]
    basins = {str(item.get("basin_fingerprint")) for item in candidates}
    lineages = {str(item.get("lineage_root")) for item in candidates}
    supports = {str(item.get("support_fingerprint")) for item in candidates}

    run_dir = root / "runs" / f"run-{run_index:03d}-{args.run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    previous_global = control.get("global_best_certificate_score")
    current_best = scores[0] if scores else None
    global_best = current_best if previous_global is None else min(float(previous_global), current_best if current_best is not None else float(previous_global))
    record_improvement = None
    if previous_global is not None and current_best is not None and float(previous_global) > 0:
        record_improvement = (float(previous_global) - min(float(previous_global), current_best)) / float(previous_global)

    history = list(control.get("best_score_history", []))
    new_history_entry = {
        "run_id": args.run_id,
        "run_index": run_index,
        "strategy_profile": profile,
        "best_certificate_score": current_best,
        "global_best_certificate_score": global_best,
        "distinct_basins": len(basins),
        "distinct_lineages": len(lineages),
        "parent_improvement_fraction": len(improved) / max(1, len(parent_based)),
        "exact_verified_count": len(exact),
    }
    prospective_history = (history + [new_history_entry])[-20:]
    gain3 = three_run_gain(prospective_history)
    no_record = record_improvement is not None and record_improvement <= 0.0
    plateau = bool(no_record or (gain3 is not None and gain3 < 0.02))
    recommended = "exact_reconstruction" if exact else (rotate_profile(profile) if plateau else profile)

    summary = {
        "schema_version": 1,
        "approach": "third-approach-2.0-multibasin-proof-certificates",
        "run_id": args.run_id,
        "run_index": run_index,
        "base_seed": int(launch["base_seed"]),
        "strategy_profile": profile,
        "accepted": accepted,
        "expected_jobs": args.expected_jobs,
        "minimum_jobs": args.min_jobs,
        "completed_jobs": completed_jobs,
        "attempts": attempts,
        "worker_errors": errors,
        "worker_error_fraction": error_fraction,
        "candidate_count": len(candidates),
        "best_certificate_score": current_best,
        "global_best_certificate_score": global_best,
        "median_saved_score": statistics.median(scores) if scores else None,
        "record_improvement_fraction": record_improvement,
        "three_run_global_gain_fraction": gain3,
        "plateau_detected": plateau,
        "recommended_next_profile": recommended,
        "lane_counts": dict(lane_counts),
        "parent_based_candidates_saved": len(parent_based),
        "parent_based_improvements_saved": len(improved),
        "parent_improvement_fraction": len(improved) / max(1, len(parent_based)),
        "distinct_basins": len(basins),
        "distinct_lineages": len(lineages),
        "distinct_supports": len(supports),
        "exact_verified_count": len(exact),
        "interpretation": "Exact verification applies only to the recorded support-restricted n=6,d=3 system; numerical candidates are not proofs.",
        "created_at": time.time(),
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_gzip_json(run_dir / "top-candidates.json.gz", {"candidates": candidates[:640]})
    write_gzip_json(run_dir / "contrast-pairs.json.gz", {"pairs": contrast_pairs(candidates)})
    write_gzip_json(run_dir / "job-manifests.json.gz", {"manifests": manifests})
    (run_dir / "README.md").write_text(
        "# Third approach 2.0 run\n\n"
        f"- GitHub Actions run: `{args.run_id}`\n"
        f"- Research index: `{run_index}`\n"
        f"- Accepted: `{accepted}` ({completed_jobs}/{args.expected_jobs} jobs)\n"
        f"- Strategy profile: `{profile}`\n"
        f"- Attempts: `{attempts}`\n"
        f"- Best coefficient-space score: `{current_best}`\n"
        f"- Distinct basins / lineages: `{len(basins)}` / `{len(lineages)}`\n"
        f"- Parent improvement fraction: `{summary['parent_improvement_fraction']}`\n"
        f"- Exact restricted certificates: `{len(exact)}`\n"
        f"- Plateau: `{plateau}`; recommended next profile: `{recommended}`\n\n"
        "The run searches and develops several proof-certificate basins. Numerical leads are not proofs.\n",
        encoding="utf-8",
    )

    bank_path = root / "candidates" / "bank.json.gz"
    previous = []
    if bank_path.exists():
        try:
            previous = list(read_gzip_json(bank_path).get("candidates", []))
        except Exception:
            previous = []
    bank = build_multibasin_bank(previous, candidates[:640], limit=1200)
    write_gzip_json(
        bank_path,
        {
            "schema_version": 1,
            "updated_from_run_id": args.run_id,
            "retention_policy": "global elite plus lineage champions plus basin champions plus current-run novelty",
            "candidates": bank,
        },
    )

    if accepted and int(control.get("last_run_id") or 0) != args.run_id:
        control.update(
            {
                "completed_runs": int(control.get("completed_runs", 0)) + 1,
                "last_run_id": args.run_id,
                "last_run_index": run_index,
                "last_run_accepted": True,
                "last_best_certificate_score": current_best,
                "global_best_certificate_score": global_best,
                "best_score_history": prospective_history,
                "next_run_index": run_index + 1,
                "next_seed": int(launch["base_seed"]) + 1_000_003,
                "current_strategy_profile": profile,
                "recommended_next_profile": recommended,
                "last_plateau_detected": plateau,
                "last_exact_verified_count": len(exact),
                "candidate_bank_size": len(bank),
            }
        )
    elif not accepted:
        control["last_run_accepted"] = False
    control_path.write_text(json.dumps(control, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
