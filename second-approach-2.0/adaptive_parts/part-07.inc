        "legacy_strategy": legacy_strategy,
        "independent_strategy": independent_strategy,
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
        "median_promoted_max_error": float(
            statistics.median(float(item["max_error"]) for item in payloads)
        ),
        "best_independent_max_error": (
            float(best_independent["max_error"]) if best_independent else None
        ),
        "best_independent_candidate_id": (
            str(best_independent.get("candidate_id")) if best_independent else None
        ),
        "best_fresh_independent_max_error": (
            float(best_fresh["max_error"]) if best_fresh else None
        ),
        "best_fresh_independent_candidate_id": (
            str(best_fresh.get("candidate_id")) if best_fresh else None
        ),
        "best_inherited_independent_max_error": (
            float(best_inherited["max_error"]) if best_inherited else None
        ),
        "best_inherited_independent_candidate_id": (
            str(best_inherited.get("candidate_id")) if best_inherited else None
        ),
        "best_candidate_id": str(optimized[0].get("candidate_id")),
        "lane_attempt_counts": dict(sorted(lane_attempt_counts.items())),
        "lane_optimized_counts": dict(sorted(lane_optimized_counts.items())),
        "lane_promoted_counts": dict(sorted(lane_promoted_counts.items())),
        "lane_best_max_error": dict(sorted(lane_best.items())),
        "families": dict(sorted(family_counts.items())),
        "strategy_counts": dict(sorted(strategy_counts.items())),
        "exact_obstruction_statuses": dict(sorted(obstruction_counts.items())),
        "distinct_support_fingerprints": len(support_fingerprints),
        "distinct_residual_basin_fingerprints": len(basin_fingerprints),
        "distinct_lineage_roots": len(lineage_roots),
        "distinct_independent_lineage_roots": len(
            {lineage_root(item) for item in independent_payloads}
        ),
        "legacy_rooted_promoted": len(old_rooted),
        "legacy_rooted_promoted_fraction": len(old_rooted) / len(payloads) if payloads else 0.0,
        "independent_promoted": len(independent_payloads),
        "fresh_independent_promoted": len(fresh_independent_payloads),
        "inherited_independent_promoted": len(inherited_independent_payloads),
        "parent_based_promoted": len(parent_based),
        "parent_based_improvements_promoted": len(parent_improvements),
        "independent_parent_based_promoted": len(independent_parent_based),
        "independent_parent_improvements_promoted": len(independent_parent_improvements),
        "independent_parent_improvement_fraction": (
            len(independent_parent_improvements) / len(independent_parent_based)
            if independent_parent_based
            else 0.0
        ),
        "legacy_parent_based_promoted": len(legacy_parent_based),
        "legacy_parent_improvements_promoted": len(legacy_parent_improvements),
        "legacy_parent_improvement_fraction": (
            len(legacy_parent_improvements) / len(legacy_parent_based)
            if legacy_parent_based
            else 0.0
        ),
        "best_independent_lineages": lineage_summary(independent_payloads),
        "best_legacy_lineages": lineage_summary(legacy_payloads, limit=20),
        "repeated_independent_top_residual_signatures": [
            {"rows": key, "count": count}
            for key, count in top_row_counts.most_common(20)
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
        with gzip.open(
            promoted_dir / f"{index:04d}-{candidate_id}.json.gz",
            "wt",
            encoding="utf-8",
            compresslevel=9,
        ) as out:
            json.dump(clean, out, sort_keys=True, separators=(",", ":"))
            out.write("\n")

    prior: list[dict[str, Any]] = []
    bank_path = root / "candidates" / "bank.json.gz"
    if bank_path.exists():
        try:
            prior = list(load_gzip_json(bank_path).get("candidates", []))
        except Exception:
            prior = []
    bank = select_bank(prior + payloads, limit=1200)
    bank_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(bank_path, "wt", encoding="utf-8", compresslevel=9) as out:
        json.dump(
            {"schema_version": 2, "candidates": bank},
            out,
            sort_keys=True,
            separators=(",", ":"),
        )
        out.write("\n")

    state_path = root / "control.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if accepted:
        state["completed_runs"] = max(int(state.get("completed_runs", 0)), run_index + 1)
        state["next_run_index"] = run_index + 1
        state["next_seed"] = int(state.get("base_seed", 20260730)) + (run_index + 1) * 1_000_003
        history = list(state.get("best_score_history", []))
        history.append(
            {
                "run_id": args.run_id,
                "run_index": run_index,
                "lane_plan_version": lane_plan_version,
                "legacy_strategy": legacy_strategy,
                "independent_strategy": independent_strategy,
                "best_max_error": summary["best_max_error"],
                "best_independent_max_error": summary["best_independent_max_error"],
                "best_fresh_independent_max_error": summary[
                    "best_fresh_independent_max_error"
                ],
                "best_inherited_independent_max_error": summary[
                    "best_inherited_independent_max_error"
                ],
                "distinct_support_fingerprints": summary[
                    "distinct_support_fingerprints"
                ],
                "distinct_residual_basin_fingerprints": summary[
                    "distinct_residual_basin_fingerprints"
                ],
