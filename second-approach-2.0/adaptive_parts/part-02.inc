                    "strategy": independent_strategy,
                }
            )
            return result

        mutation_mode = {
            "balanced": "balanced",
            "precision_heavy": "micro",
            "mutation_heavy": "balanced",
            "escape_heavy": "escape",
        }[independent_strategy]
        initial_x = result["initial_x"]
        if independent_strategy == "escape_heavy" and rng.random() < 0.35:
            initial_x = None
        result.update(
            {
                "mask": mutate_support(
                    model, mask_from_candidate(parent), rng, mutation_mode
                ),
                "family": f"independent_mutation_{independent_strategy}",
                "strategy": independent_strategy,
                "initial_x": initial_x,
            }
        )
        return result

    if lane == "legacy_control":  # Backward-compatible lane plan v1.
        parent = rank_weighted_parent(rng, legacy_bank, limit=100)
        if parent is None:
            mask, family = fresh_support(model, rng)
            return _fresh_result(mask, "legacy_control_fallback_" + family)
        result = parent_payload(model, parent)
        result.update(
            {
                "mask": model.mutate_seed_support(mask_from_candidate(parent), rng),
                "family": "legacy_control_mutation",
                "legacy_rooted": True,
                "lineage_origin": "legacy",
                "strategy": "legacy_v1",
            }
        )
        return result

    if lane == "precision_audit":  # Backward-compatible lane plan v1.
        pool = new_bank if new_bank else legacy_bank
        parent = rank_weighted_parent(rng, pool, limit=200)
        if parent is None:
            mask, family = fresh_support(model, rng)
            return _fresh_result(mask, "precision_audit_fallback_" + family)
        result = parent_payload(model, parent)
        result.update(
            {
                "mask": mask_from_candidate(parent),
                "family": "precision_audit",
                "strategy": "precision_v1",
            }
        )
        return result

    if lane in {"legacy_adaptive", "legacy_escape", "legacy_precision"}:
        legacy_pool = legacy_bank + [
            item for item in new_bank if not is_independent_candidate(item)
        ]
        parent = choose_diverse_parent(
            rng,
            legacy_pool,
            independent_only=False,
            global_worker_id=global_worker_id,
            run_index=run_index,
            attempt=attempt,
            limit=96,
        )
        if parent is None:
            mask, family = fresh_support(model, rng)
            fallback = _fresh_result(mask, f"{lane}_fallback_{family}")
            fallback.update({"legacy_rooted": True, "lineage_origin": "legacy"})
            return fallback
        result = parent_payload(model, parent)
        result.update({"legacy_rooted": True, "lineage_origin": "legacy"})

        strategy = legacy_strategy
        if lane == "legacy_precision":
            strategy = "micro_polish"
        elif lane == "legacy_escape":
            strategy = (
                "residual_escape"
                if legacy_strategy in {"micro_polish", "bound_expansion"}
                else "wide_restart"
            )

        parent_mask = mask_from_candidate(parent)
        initial_x = result["initial_x"]
        if strategy in {"micro_polish", "bound_expansion"}:
            mask = parent_mask
        elif strategy == "support_mutation":
            mask = mutate_support(model, parent_mask, rng, "balanced")
        elif strategy == "residual_escape":
            mask = mutate_support(model, parent_mask, rng, "escape")
        elif strategy == "wide_restart":
            mask = mutate_support(model, parent_mask, rng, "micro")
            initial_x = None
        else:  # pragma: no cover - guarded above.
            raise ValueError(strategy)
        result.update(
            {
                "mask": mask,
                "family": f"{lane}_{strategy}",
                "strategy": strategy,
                "initial_x": initial_x,
            }
        )
        return result

    raise ValueError(f"unknown lane {lane}")


def residual_signature(
    model, x: np.ndarray, limit: int = 12
) -> tuple[list[dict[str, Any]], str]:
    amp = model.amplitudes(x)
    errors = np.abs(amp - model.TARGET)
    mixed = [(int(row), float(errors[int(row)])) for row in model.MIXED_ROWS]
    mixed.sort(key=lambda item: item[1], reverse=True)
    top = []
    for row, value in mixed[:limit]:
        top.append(
            {
                "row": row,
                "colouring": [int(v) for v in model.COLOURINGS[row]],
                "abs_error": value,
            }
        )
    bucket = tuple(item["row"] for item in top[:6])
    fingerprint = hashlib.sha256(repr(bucket).encode("utf-8")).hexdigest()[:20]
    return top, fingerprint


def support_fingerprint(mask: int) -> str:
    return hashlib.sha256(f"{int(mask):x}".encode("ascii")).hexdigest()[:20]


# ---- runner implementation ----

def atomic_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def append_jsonl(path: Path, document: dict) -> None:
    with path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n")
        out.flush()
        os.fsync(out.fileno())


def complex_pairs(values: np.ndarray) -> list[list[float]]:
    return [[float(z.real), float(z.imag)] for z in values]


def sanitize_initial_x(
    initial_x: np.ndarray | None,
    bound: float,
) -> tuple[np.ndarray | None, int]:
    """Move inherited weights away from the numerical box boundary."""
    if initial_x is None:
        return None, 0
    values = np.asarray(initial_x, dtype=np.complex128).copy()
    margin = max(0.25, 0.05 * float(bound))
    limit = max(0.0, float(bound) - margin)
    clipped_real = np.clip(values.real, -limit, limit)
    clipped_imag = np.clip(values.imag, -limit, limit)
    changed = int(
        np.count_nonzero(clipped_real != values.real)
        + np.count_nonzero(clipped_imag != values.imag)
    )
    return clipped_real + 1j * clipped_imag, changed


def solve_support_with_bound_safe_start(
    model,
    mask: int,
    rng: np.random.Generator,
    *,
    max_nfev: int,
    scale: float,
    bound: float,
    initial_x: np.ndarray | None,
) -> tuple[dict, int]:
    """Clip the constructed real start vector strictly inside SciPy bounds."""
    original = model.structured_initial_point
    clipped_coordinates = 0
    lower = np.nextafter(-float(bound), np.inf)
    upper = np.nextafter(float(bound), -np.inf)

    def bound_safe_initial_point(*args, **kwargs):
        nonlocal clipped_coordinates
        y0 = np.asarray(original(*args, **kwargs), dtype=float)
        safe = np.clip(y0, lower, upper)
        clipped_coordinates += int(np.count_nonzero(safe != y0))
        return safe

    model.structured_initial_point = bound_safe_initial_point
    try:
        result = model.solve_support(
            mask,
            rng,
            max_nfev=max_nfev,
            scale=scale,
            bound=bound,
            initial_x=initial_x,
        )
    finally:
        model.structured_initial_point = original
    return result, clipped_coordinates


def solver_profile(
    lane: str,
    *,
    max_nfev: int,
    max_attempts: int,
    legacy_strategy: str,
    independent_strategy: str,
) -> tuple[int, float, float]:
    """Return evaluation budget, perturbation scale, and box bound."""
    base = int(max_nfev)
    profile = (base, 0.12, 8.0)

    if lane in {"precision_audit", "independent_precision"}:
