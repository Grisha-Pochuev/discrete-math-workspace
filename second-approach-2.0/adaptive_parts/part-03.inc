        profile = (max(900, base * 3), 0.025, 16.0)
    elif lane == "independent_mutation":
        profile = {
            "balanced": (max(600, base * 2), 0.06, 12.0),
            "precision_heavy": (max(900, base * 3), 0.03, 16.0),
            "mutation_heavy": (max(600, base * 2), 0.09, 16.0),
            "escape_heavy": (max(450, int(base * 1.5)), 0.16, 20.0),
        }[independent_strategy]
    elif lane in {"legacy_adaptive", "legacy_escape", "legacy_precision"}:
        strategy = legacy_strategy
        if lane == "legacy_precision":
            strategy = "micro_polish"
        elif lane == "legacy_escape":
            strategy = (
                "residual_escape"
                if legacy_strategy in {"micro_polish", "bound_expansion"}
                else "wide_restart"
            )
        profile = {
            "micro_polish": (max(1500, base * 5), 0.012, 20.0),
            "support_mutation": (max(750, int(base * 2.5)), 0.055, 14.0),
            "wide_restart": (max(900, base * 3), 0.28, 24.0),
            "bound_expansion": (max(1500, base * 5), 0.018, 32.0),
            "residual_escape": (max(600, base * 2), 0.13, 20.0),
        }[strategy]

    # Smoke runs set a positive attempt cap. They must exercise every branch
    # without inheriting production-size minimum budgets.
    if max_attempts > 0:
        profile = (max(10, base), profile[1], profile[2])
    return profile


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
    lane_plan_version: int,
    legacy_strategy: str,
    independent_strategy: str,
) -> None:
    repo_path = Path(repo)
    root = Path(output) / f"worker-{worker_id}"
    root.mkdir(parents=True, exist_ok=True)
    attempts_path = root / "attempts.jsonl"
    model = engine.load_legacy_model(repo_path)
    exact = engine.load_exact_analyser(repo_path)
    legacy_bank = engine.load_bank(
        repo_path / "second-approach" / "candidates" / "seed-bank.json.gz"
    )
    new_bank = engine.load_bank(
        repo_path / "second-approach-2.0" / "candidates" / "bank.json.gz"
    )
    lane = engine.lane_for(job_id, worker_id, lane_plan_version)
    global_worker_id = job_id * 4 + worker_id
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
        error_context: dict = {
            "lane": lane,
            "lane_plan_version": lane_plan_version,
            "legacy_strategy": legacy_strategy,
            "independent_strategy": independent_strategy,
        }
        try:
            selection = engine.choose_support(
                model,
                exact,
                local,
                lane,
                legacy_bank,
                new_bank,
                run_index=run_index,
                global_worker_id=global_worker_id,
                attempt=attempt,
                legacy_strategy=legacy_strategy,
                independent_strategy=independent_strategy,
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
                and lane != "obstruction_boundary"
                and attempt % 5 != 0
            )
            base_record = {
                "attempt": attempt,
                "seed": seed,
                "lane": lane,
                "lane_plan_version": lane_plan_version,
                "legacy_strategy": legacy_strategy,
                "independent_strategy": independent_strategy,
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

            solve_nfev, scale, bound = solver_profile(
                lane,
                max_nfev=max_nfev,
                max_attempts=max_attempts,
                legacy_strategy=legacy_strategy,
                independent_strategy=independent_strategy,
            )
            initial_x, inherited_clipped = sanitize_initial_x(initial_x, bound)
            result, constructed_clipped = solve_support_with_bound_safe_start(
                model,
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
            improvement_fraction = None
            if parent_score is not None and float(parent_score) > 0:
                improvement_fraction = (
                    float(parent_score) - float(result["max_error"])
                ) / float(parent_score)
            improved_parent = bool(
                improvement_fraction is not None and improvement_fraction > 0
            )
            summary = {
                **base_record,
                "candidate_id": candidate_id,
                "skipped_known_obstruction": False,
                "solver_max_nfev": solve_nfev,
                "solver_scale": scale,
                "solver_bound": bound,
                "inherited_initial_point_clipped_coordinates": inherited_clipped,
                "constructed_initial_point_clipped_coordinates": constructed_clipped,
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
