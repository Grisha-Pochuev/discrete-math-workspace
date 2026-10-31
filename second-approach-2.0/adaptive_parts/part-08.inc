                "distinct_independent_lineage_roots": summary[
                    "distinct_independent_lineage_roots"
                ],
                "legacy_rooted_promoted_fraction": summary[
                    "legacy_rooted_promoted_fraction"
                ],
                "independent_parent_improvement_fraction": summary[
                    "independent_parent_improvement_fraction"
                ],
                "legacy_parent_improvement_fraction": summary[
                    "legacy_parent_improvement_fraction"
                ],
                "lane_best_max_error": summary["lane_best_max_error"],
            }
        )
        state["best_score_history"] = history[-50:]

        def update_global(error_key: str, candidate_key: str, value, candidate_id) -> None:
            if value is None:
                return
            current = state.get(error_key)
            if current is None or float(value) < float(current):
                state[error_key] = float(value)
                state[candidate_key] = candidate_id

        update_global(
            "global_best_max_error",
            "global_best_candidate_id",
            summary["best_max_error"],
            summary["best_candidate_id"],
        )
        update_global(
            "global_best_independent_max_error",
            "global_best_independent_candidate_id",
            summary["best_independent_max_error"],
            summary["best_independent_candidate_id"],
        )
        update_global(
            "global_best_fresh_independent_max_error",
            "global_best_fresh_independent_candidate_id",
            summary["best_fresh_independent_max_error"],
            summary["best_fresh_independent_candidate_id"],
        )
        update_global(
            "global_best_inherited_independent_max_error",
            "global_best_inherited_independent_candidate_id",
            summary["best_inherited_independent_max_error"],
            summary["best_inherited_independent_candidate_id"],
        )
    else:
        state["next_run_index"] = run_index
        state["next_seed"] = int(state.get("next_seed", base_seed)) + 97
    state["last_run_id"] = args.run_id
    state["last_run_index"] = run_index
    state["last_conclusion"] = args.conclusion
    state["last_run_accepted"] = accepted
    state["last_lane_plan_version"] = lane_plan_version
    state["last_legacy_strategy"] = legacy_strategy
    state["last_independent_strategy"] = independent_strategy
    state["candidate_bank_size"] = len(bank)
    state["candidate_bank_independent_size"] = sum(is_independent(item) for item in bank)
    state["candidate_bank_legacy_size"] = sum(not is_independent(item) for item in bank)
    atomic_json(state_path, state)

    readme = [
        f"# Second approach 2.0 run {run_index:03d}",
        "",
        f"- GitHub Actions run: `{args.run_id}`",
        f"- accepted: `{accepted}`",
        f"- jobs present: {len(job_ids)}/{args.expected_jobs}",
        f"- lane plan version: {lane_plan_version}",
        f"- legacy strategy: `{legacy_strategy}`",
        f"- independent strategy: `{independent_strategy}`",
        f"- total attempts: {len(attempts)}",
        f"- optimized attempts: {len(optimized)}",
        f"- promoted candidates: {len(payloads)}",
        f"- best maximum equation error: {summary['best_max_error']!r}",
        f"- best independent maximum equation error: {summary['best_independent_max_error']!r}",
        f"- best fresh independent error: {summary['best_fresh_independent_max_error']!r}",
        f"- best inherited independent error: {summary['best_inherited_independent_max_error']!r}",
        f"- distinct independent lineages: {summary['distinct_independent_lineage_roots']}",
        f"- independent parent improvement fraction: {summary['independent_parent_improvement_fraction']:.6f}",
        f"- legacy parent improvement fraction: {summary['legacy_parent_improvement_fraction']:.6f}",
        f"- distinct support fingerprints: {summary['distinct_support_fingerprints']}",
        f"- distinct residual-basin fingerprints: {summary['distinct_residual_basin_fingerprints']}",
        f"- worker errors: {len(failures)}",
        "",
        "This archive is numerical evidence only, not a counterexample. See `summary.json` for lineage, tactic, lane, and residual comparisons.",
    ]
    (output / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")

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


