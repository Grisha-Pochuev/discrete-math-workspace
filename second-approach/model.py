#!/usr/bin/env python3
"""Numerical model and dense-support generators for the n=6, d=3 Krenn--Gu case."""
from __future__ import annotations

import itertools

import numpy as np
from scipy.optimize import least_squares
from scipy.sparse import csr_matrix

N = 6
D = 3
MATCHINGS: tuple[tuple[tuple[int, int], ...], ...]


def perfect_matchings(vertices: tuple[int, ...]):
    if not vertices:
        yield ()
        return
    i = vertices[0]
    for p in range(1, len(vertices)):
        j = vertices[p]
        rest = vertices[1:p] + vertices[p + 1 :]
        for tail in perfect_matchings(rest):
            yield ((i, j),) + tail


MATCHINGS = tuple(perfect_matchings(tuple(range(N))))
COLOURINGS = np.asarray(tuple(itertools.product(range(D), repeat=N)), dtype=np.int8)
EDGES = tuple((i, j) for i in range(N) for j in range(i + 1, N))
EDGE_POS = {edge: index for index, edge in enumerate(EDGES)}
NV = len(EDGES) * D * D
NC = len(COLOURINGS)
MONO = np.asarray((0, 364, 728), dtype=np.int16)
MONO_SET = frozenset(map(int, MONO))
ALL_MASK = (1 << NV) - 1


def var_index(i: int, j: int, a: int, b: int) -> int:
    if i > j:
        i, j, a, b = j, i, b, a
    return (EDGE_POS[(i, j)] * D + a) * D + b


TERM_VARS = np.empty((NC, len(MATCHINGS), N // 2), dtype=np.int16)
for ci, colours in enumerate(COLOURINGS):
    for mi, matching in enumerate(MATCHINGS):
        TERM_VARS[ci, mi] = [
            var_index(i, j, int(colours[i]), int(colours[j]))
            for i, j in matching
        ]

TARGET = np.zeros(NC, dtype=np.complex128)
TARGET[MONO] = 1.0
MIXED_ROWS = np.asarray([i for i in range(NC) if i not in MONO_SET], dtype=np.int16)


def active_terms(mask: int) -> np.ndarray:
    support = np.zeros(NV, dtype=bool)
    support[[k for k in range(NV) if (mask >> k) & 1]] = True
    return np.all(support[TERM_VARS], axis=2)


def has_mono_targets(mask: int) -> bool:
    active = active_terms(mask)
    return bool(np.all(np.any(active[MONO], axis=1)))


def is_closed(mask: int) -> bool:
    counts = active_terms(mask).sum(axis=1)
    return not np.any(counts[MIXED_ROWS] == 1)


def _add_target_matchings(mask: int, rng: np.random.Generator) -> int:
    for colour, row in enumerate(MONO):
        active = active_terms(mask)[int(row)]
        if np.any(active):
            continue
        matching = MATCHINGS[int(rng.integers(len(MATCHINGS)))]
        for i, j in matching:
            mask |= 1 << var_index(i, j, colour, colour)
    return mask


def close_support(mask: int, rng: np.random.Generator, max_steps: int = 1000) -> int:
    """Grow a support until every mixed row has either 0 or at least 2 active terms."""
    mask = _add_target_matchings(mask, rng)
    for _ in range(max_steps):
        active = active_terms(mask)
        counts = active.sum(axis=1)
        singleton = [int(row) for row in MIXED_ROWS if counts[int(row)] == 1]
        if not singleton:
            return mask
        row = singleton[int(rng.integers(len(singleton)))]
        inactive_terms = np.flatnonzero(~active[row])
        choices: list[tuple[int, int, list[int]]] = []
        for term in inactive_terms:
            missing = sorted({
                int(v) for v in TERM_VARS[row, int(term)] if not ((mask >> int(v)) & 1)
            })
            if missing:
                choices.append((len(missing), int(term), missing))
        if not choices:
            raise RuntimeError("singleton row has no activatable second term")
        best_missing = min(item[0] for item in choices)
        shortlist = [item for item in choices if item[0] <= best_missing + 1]
        _, _, missing = shortlist[int(rng.integers(len(shortlist)))]
        for variable in missing:
            mask |= 1 << variable
    raise RuntimeError("closure growth did not converge")


def prune_support(mask: int, rng: np.random.Generator, target_size: int) -> int:
    """Remove variables greedily while preserving closure and all three targets."""
    variables = [k for k in range(NV) if (mask >> k) & 1]
    rng.shuffle(variables)
    for variable in variables:
        if mask.bit_count() <= target_size:
            break
        trial = mask & ~(1 << variable)
        if has_mono_targets(trial) and is_closed(trial):
            mask = trial
    return mask


def random_dense_closed_support(
    rng: np.random.Generator,
    target_size: int,
    *,
    min_seed_size: int = 24,
) -> int:
    target_size = int(np.clip(target_size, 21, NV))
    seed_size = min(target_size, max(min_seed_size, target_size // 2))
    chosen = rng.choice(NV, size=seed_size, replace=False)
    mask = 0
    for variable in chosen:
        mask |= 1 << int(variable)
    mask = close_support(mask, rng)
    if mask.bit_count() < target_size:
        missing = [k for k in range(NV) if not ((mask >> k) & 1)]
        rng.shuffle(missing)
        for variable in missing[: target_size - mask.bit_count()]:
            mask |= 1 << variable
    mask = prune_support(mask, rng, target_size)
    assert has_mono_targets(mask)
    assert is_closed(mask)
    return mask


def near_full_support(rng: np.random.Generator, drop: int) -> int:
    target = max(21, NV - int(drop))
    return prune_support(ALL_MASK, rng, target)


def mutate_seed_support(mask: int, rng: np.random.Generator) -> int:
    """Perturb a preserved near-solution without destroying the closure condition."""
    if rng.random() < 0.45:
        return mask
    missing = [k for k in range(NV) if not ((mask >> k) & 1)]
    rng.shuffle(missing)
    for variable in missing[: int(rng.integers(1, min(9, len(missing) + 1)))]:
        mask |= 1 << variable
    active = [k for k in range(NV) if (mask >> k) & 1]
    rng.shuffle(active)
    for variable in active[: int(rng.integers(0, 4))]:
        trial = mask & ~(1 << variable)
        if has_mono_targets(trial) and is_closed(trial):
            mask = trial
    return mask


def choose_support(
    rng: np.random.Generator,
    run_index: int,
    attempt: int,
    seed_candidates: list[dict] | None = None,
) -> tuple[int, str, np.ndarray | None, str | None]:
    """Rotate dense families and periodically refine preserved near-solutions."""
    lane = (run_index + attempt) % 6
    if lane == 0:
        return ALL_MASK, "full", None, None
    if lane == 1:
        drop = int(rng.integers(5, 26))
        return near_full_support(rng, drop), "near_full", None, None
    if lane == 2:
        target = int(rng.integers(31, 51))
        return random_dense_closed_support(rng, target), "closure_growth_low_seed", None, None
    if lane == 3:
        target = int(rng.integers(51, 81))
        return random_dense_closed_support(rng, target), "closure_growth_medium_seed", None, None
    if lane == 4:
        target = int(rng.integers(96, 126))
        return random_dense_closed_support(rng, target), "dense_random", None, None
    if seed_candidates:
        parent = seed_candidates[int(rng.integers(len(seed_candidates)))]
        mask = mutate_seed_support(int(str(parent["support_mask_hex"]), 16), rng)
        x = np.zeros(NV, dtype=np.complex128)
        for variable, pair in zip(parent.get("active_variables", []), parent.get("active_weights", [])):
            x[int(variable)] = complex(float(pair[0]), float(pair[1]))
        return mask, "seed_bank_mutation", x, str(parent.get("candidate_id", "unknown"))
    return ALL_MASK, "full_fallback", None, None


def amplitudes(x: np.ndarray) -> np.ndarray:
    return np.prod(x[TERM_VARS], axis=2).sum(axis=1)


def structured_initial_point(
    active: np.ndarray,
    mask: int,
    rng: np.random.Generator,
    scale: float,
    initial_x: np.ndarray | None = None,
) -> np.ndarray:
    x = np.zeros(NV, dtype=np.complex128)
    if initial_x is not None:
        x[active] = np.asarray(initial_x, dtype=np.complex128)[active]
        x[active] += 0.03 * scale * (
            rng.standard_normal(len(active)) + 1j * rng.standard_normal(len(active))
        )
    else:
        x[active] = scale * (
            rng.standard_normal(len(active)) + 1j * rng.standard_normal(len(active))
        )
    active_matrix = active_terms(mask)
    for colour, row in enumerate(MONO):
        choices = np.flatnonzero(active_matrix[int(row)])
        if not len(choices):
            raise ValueError("support has no monochromatic target matching")
        matching = MATCHINGS[int(choices[int(rng.integers(len(choices)))])]
        phase = np.exp(2j * np.pi * rng.random())
        root = phase ** (1 / 3)
        for i, j in matching:
            variable = var_index(i, j, colour, colour)
            if (mask >> variable) & 1:
                x[variable] += root
    return np.concatenate((x[active].real, x[active].imag))


def solve_support(
    mask: int,
    rng: np.random.Generator,
    *,
    max_nfev: int = 300,
    scale: float = 0.12,
    bound: float = 8.0,
    initial_x: np.ndarray | None = None,
) -> dict:
    active = np.asarray([k for k in range(NV) if (mask >> k) & 1], dtype=np.int16)
    n_active = len(active)
    support_bool = np.zeros(NV, dtype=bool)
    support_bool[active] = True
    term_active = np.all(support_bool[TERM_VARS], axis=2)
    rows = np.flatnonzero(np.any(term_active, axis=1) | (np.abs(TARGET) > 0))

    def unpack(y: np.ndarray) -> np.ndarray:
        x = np.zeros(NV, dtype=np.complex128)
        x[active] = y[:n_active] + 1j * y[n_active:]
        return x

    def residual(y: np.ndarray) -> np.ndarray:
        r = amplitudes(unpack(y))[rows] - TARGET[rows]
        return np.concatenate((r.real, r.imag))

    def jacobian(y: np.ndarray) -> csr_matrix:
        x = unpack(y)
        deriv = np.zeros((len(rows), NV), dtype=np.complex128)
        for k in range(N // 2):
            other = [q for q in range(N // 2) if q != k]
            vals = np.prod(x[TERM_VARS[rows][:, :, other]], axis=2)
            rr = np.repeat(np.arange(len(rows)), len(MATCHINGS))
            cc = TERM_VARS[rows, :, k].ravel()
            np.add.at(deriv, (rr, cc), vals.ravel())
        deriv = deriv[:, active]
        rr, cc = np.nonzero(deriv)
        z = deriv[rr, cc]
        out_rows = np.concatenate((rr, rr, rr + len(rows), rr + len(rows)))
        out_cols = np.concatenate((cc, cc + n_active, cc, cc + n_active))
        data = np.concatenate((z.real, -z.imag, z.imag, z.real))
        return csr_matrix(
            (data, (out_rows, out_cols)),
            shape=(2 * len(rows), 2 * n_active),
        )

    y0 = structured_initial_point(active, mask, rng, scale, initial_x=initial_x)
    ans = least_squares(
        residual,
        y0,
        jac=jacobian,
        method="trf",
        x_scale="jac",
        bounds=(-bound, bound),
        ftol=1e-11,
        xtol=1e-11,
        gtol=1e-11,
        max_nfev=max_nfev,
        verbose=0,
    )
    x = unpack(ans.x)
    amp = amplitudes(x)
    mixed_abs = np.abs(amp[MIXED_ROWS])
    mono_error = np.abs(amp[MONO] - 1.0)
    full_error = np.abs(amp - TARGET)
    active_abs = np.abs(x[active])
    return {
        "x": x,
        "active": active,
        "rows": rows,
        "status": int(ans.status),
        "message": str(ans.message),
        "nfev": int(ans.nfev),
        "cost": float(ans.cost),
        "total_l2": float(np.linalg.norm(full_error)),
        "max_error": float(np.max(full_error)),
        "mixed_l2": float(np.linalg.norm(mixed_abs)),
        "mixed_max": float(np.max(mixed_abs)),
        "mono_max_error": float(np.max(mono_error)),
        "mono_amplitudes": amp[MONO],
        "weight_max_abs": float(np.max(active_abs)),
        "weight_min_abs": float(np.min(active_abs)),
        "optimality": float(ans.optimality),
        "success": bool(np.max(full_error) < 1e-8),
    }
