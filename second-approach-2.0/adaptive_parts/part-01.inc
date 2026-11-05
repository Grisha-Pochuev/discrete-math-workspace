    # Keep a worker on one lineage for a short block of attempts, then rotate.
    slot = (
        int(global_worker_id)
        + int(run_index) * 5
        + int(attempt) // 8
    ) % focus_count
    if rng.random() < 0.78:
        return representatives[slot]
    return rank_weighted_parent(rng, representatives, limit=focus_count)


def fresh_support(model, rng: np.random.Generator) -> tuple[int, str]:
    choice = int(rng.integers(0, 5))
    if choice == 0:
        return model.ALL_MASK, "fresh_full"
    if choice == 1:
        return (
            model.near_full_support(rng, int(rng.integers(5, 36))),
            "fresh_near_full",
        )
    if choice == 2:
        target = int(rng.integers(31, 56))
        return model.random_dense_closed_support(rng, target), "fresh_closed_31_55"
    if choice == 3:
        target = int(rng.integers(56, 91))
        return model.random_dense_closed_support(rng, target), "fresh_closed_56_90"
    target = int(rng.integers(91, 126))
    return model.random_dense_closed_support(rng, target), "fresh_closed_91_125"


def exact_status(model, exact, mask: int) -> tuple[str, int]:
    counts = model.active_terms(mask).sum(axis=1)
    binary_rows = int(sum(int(counts[row]) == 2 for row in model.MIXED_ROWS))
    if binary_rows == 0:
        return "unresolved_no_binary_relations", binary_rows
    if mask.bit_count() <= 60 and binary_rows <= 24:
        try:
            return str(exact.analyse_support(mask)), binary_rows
        except Exception as exc:
            return f"exact_analyser_error:{type(exc).__name__}", binary_rows
    return "not_checked_dense", binary_rows


def obstruction_boundary_support(
    model, exact, rng: np.random.Generator
) -> dict[str, Any]:
    fallback: dict[str, Any] | None = None
    for _ in range(18):
        target = int(rng.integers(27, 61))
        base = model.random_dense_closed_support(rng, target)
        status, binary_rows = exact_status(model, exact, base)
        fallback = {
            "mask": base,
            "family": "boundary_fallback",
            "boundary_source_obstruction": status,
            "boundary_edit_distance": 0,
            "binary_relation_rows_before": binary_rows,
        }
        if status not in KNOWN_OBSTRUCTIONS:
            continue
        missing = [k for k in range(model.NV) if not ((base >> k) & 1)]
        rng.shuffle(missing)
        max_add = min(len(missing), int(rng.integers(1, 6)))
        trial = base
        for edit_count, variable in enumerate(missing[:max_add], start=1):
            trial |= 1 << int(variable)
            trial_status, trial_binary = exact_status(model, exact, trial)
            if trial_status != status or edit_count == max_add:
                return {
                    "mask": trial,
                    "family": "obstruction_boundary",
                    "boundary_source_obstruction": status,
                    "boundary_result_status": trial_status,
                    "boundary_edit_distance": edit_count,
                    "binary_relation_rows_before": binary_rows,
                    "binary_relation_rows_after": trial_binary,
                }
    assert fallback is not None
    return fallback


def novelty_support(
    model, rng: np.random.Generator, references: list[int]
) -> dict[str, Any]:
    best: tuple[int, int, str] | None = None
    sample_refs = references[:400]
    for _ in range(10):
        mask, family = fresh_support(model, rng)
        distance = (
            min(hamming_distance(mask, ref) for ref in sample_refs)
            if sample_refs
            else model.NV
        )
        if best is None or distance > best[0]:
            best = (distance, mask, family)
    assert best is not None
    return {
        "mask": best[1],
        "family": "novelty_far_" + best[2],
        "nearest_bank_hamming_distance": best[0],
    }


def parent_payload(model, parent: dict[str, Any]) -> dict[str, Any]:
    independent = is_independent_candidate(parent)
    return {
        "parent_candidate_id": str(parent.get("candidate_id", "unknown")),
        "parent_max_error": float(parent.get("max_error", 1e300)),
        "parent_lineage_depth": int(parent.get("lineage_depth", 0) or 0),
        "lineage_depth": int(parent.get("lineage_depth", 0) or 0) + 1,
        "lineage_root": candidate_lineage_root(parent),
        "lineage_origin": "independent" if independent else "legacy",
        "legacy_rooted": not independent,
        "initial_x": candidate_vector(model, parent),
    }


def mutate_support(
    model,
    mask: int,
    rng: np.random.Generator,
    mode: str,
) -> int:
    if mode == "micro":
        return model.mutate_seed_support(mask, rng)
    if mode == "balanced":
        for _ in range(int(rng.integers(1, 3))):
            mask = model.mutate_seed_support(mask, rng)
        return mask
    if mode == "escape":
        for _ in range(int(rng.integers(2, 5))):
            mask = model.mutate_seed_support(mask, rng)
        # A direct addition gives access to neighbouring dense supports even
        # when the legacy mutation happens to return its parent unchanged.
        missing = [k for k in range(model.NV) if not ((mask >> k) & 1)]
        rng.shuffle(missing)
        for variable in missing[: int(rng.integers(1, min(9, len(missing) + 1)))]:
            mask |= 1 << int(variable)
        return model.close_support(mask, rng)
    raise ValueError(f"unknown support mutation mode: {mode}")


def _fresh_result(mask: int, family: str) -> dict[str, Any]:
    return {
        "mask": mask,
        "family": family,
        "initial_x": None,
        "lineage_root": None,
        "lineage_depth": 0,
        "lineage_origin": "independent",
        "legacy_rooted": False,
    }


def choose_support(
    model,
    exact,
    rng: np.random.Generator,
    lane: str,
    legacy_bank: list[dict[str, Any]],
    new_bank: list[dict[str, Any]],
    *,
    run_index: int = 0,
    global_worker_id: int = 0,
    attempt: int = 0,
    legacy_strategy: str = "micro_polish",
    independent_strategy: str = "balanced",
) -> dict[str, Any]:
    if legacy_strategy not in ALLOWED_LEGACY_STRATEGIES:
        raise ValueError(f"unknown legacy strategy: {legacy_strategy}")
    if independent_strategy not in ALLOWED_INDEPENDENT_STRATEGIES:
        raise ValueError(f"unknown independent strategy: {independent_strategy}")

    references = [
        mask_from_candidate(item)
        for item in (legacy_bank[:200] + new_bank[:400])
        if item.get("support_mask_hex")
    ]
    if lane == "fresh_independent":
        mask, family = fresh_support(model, rng)
        return _fresh_result(mask, family)
    if lane == "obstruction_boundary":
        result = obstruction_boundary_support(model, exact, rng)
        result.update(_fresh_result(int(result["mask"]), str(result["family"])))
        return result
    if lane == "novelty_far":
        result = novelty_support(model, rng, references)
        result.update(_fresh_result(int(result["mask"]), str(result["family"])))
        return result

    if lane in INHERITED_INDEPENDENT_LANES:
        parent = choose_diverse_parent(
            rng,
            new_bank,
            independent_only=True,
            global_worker_id=global_worker_id,
            run_index=run_index,
            attempt=attempt,
            limit=128,
        )
        if parent is None:
            mask, family = fresh_support(model, rng)
            return _fresh_result(mask, f"{lane}_fallback_{family}")
        result = parent_payload(model, parent)
        if lane == "independent_precision":
            result.update(
                {
                    "mask": mask_from_candidate(parent),
                    "family": "independent_precision",
