#!/usr/bin/env python3
"""Numerical search for low-degree Nullstellensatz-style certificates.

This module works with the n=6, d=3 Krenn--Gu polynomial system. It searches
restricted support families for identities of the form

    1 ~= sum_i q_i(x) F_i(x),

where F_i are GHZ equations and q_i are affine holomorphic multipliers. A
small residual is evidence for an exact certificate worth reconstructing; it
is not itself a proof.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Any

import numpy as np
from scipy import linalg

N = 6
D = 3
EDGES = [(i, j) for i in range(N) for j in range(i + 1, N)]
EDGE_INDEX = {edge: k for k, edge in enumerate(EDGES)}
VARIABLE_COUNT = len(EDGES) * D * D
ALL_VARIABLES = np.arange(VARIABLE_COUNT, dtype=np.int16)


def _perfect_matchings(vertices: tuple[int, ...]) -> list[tuple[tuple[int, int], ...]]:
    if not vertices:
        return [tuple()]
    first = vertices[0]
    out: list[tuple[tuple[int, int], ...]] = []
    for pos in range(1, len(vertices)):
        second = vertices[pos]
        rest = vertices[1:pos] + vertices[pos + 1 :]
        edge = (min(first, second), max(first, second))
        for tail in _perfect_matchings(rest):
            out.append((edge,) + tail)
    return out


MATCHINGS = _perfect_matchings(tuple(range(N)))
COLORINGS = np.asarray(list(product(range(D), repeat=N)), dtype=np.int8)
MONO_ROWS = np.asarray(
    [sum(c * (D ** (N - 1 - k)) for k in range(N)) for c in range(D)],
    dtype=np.int32,
)
TARGET = np.zeros(D**N, dtype=np.complex128)
TARGET[MONO_ROWS] = 1.0


def variable_index(i: int, j: int, a: int, b: int) -> int:
    if i > j:
        i, j, a, b = j, i, b, a
    return EDGE_INDEX[(i, j)] * D * D + a * D + b


TERM_INDICES = np.empty((D**N, len(MATCHINGS), N // 2), dtype=np.int16)
for row, coloring in enumerate(COLORINGS):
    for mid, matching in enumerate(MATCHINGS):
        TERM_INDICES[row, mid] = [
            variable_index(i, j, int(coloring[i]), int(coloring[j]))
            for i, j in matching
        ]


@dataclass(frozen=True)
class SearchShape:
    support_size: int
    equation_limit: int
    multiplier_count: int
    train_samples: int
    validation_samples: int


def _mono_matching_variables(
    rng: np.random.Generator, support: set[int], color: int
) -> set[int]:
    active = []
    for matching in MATCHINGS:
        variables = {variable_index(i, j, color, color) for i, j in matching}
        if variables.issubset(support):
            active.append(variables)
    if active:
        return set(active[int(rng.integers(0, len(active)))])
    matching = MATCHINGS[int(rng.integers(0, len(MATCHINGS)))]
    return {variable_index(i, j, color, color) for i, j in matching}


def support_template(
    rng: np.random.Generator,
    support_size: int,
    *,
    parent_support: list[int] | np.ndarray | None = None,
    mutation_fraction: float = 0.25,
) -> np.ndarray:
    """Create a balanced support, fresh or by mutating a previous candidate.

    Every returned support contains a complete monochromatic perfect matching
    for each color. Parent mutation never removes all such witnesses.
    """
    target_size = int(np.clip(support_size, 9, VARIABLE_COUNT))
    if parent_support is None:
        support: set[int] = set()
    else:
        support = {
            int(value)
            for value in parent_support
            if 0 <= int(value) < VARIABLE_COUNT
        }

    mandatory: set[int] = set()
    for color in range(D):
        witness = _mono_matching_variables(rng, support, color)
        support.update(witness)
        mandatory.update(witness)

    if parent_support is not None and support:
        replacement_count = max(
            1, int(round(target_size * float(np.clip(mutation_fraction, 0.02, 0.80))))
        )
        removable = np.asarray(sorted(support - mandatory), dtype=np.int16)
        if len(removable):
            remove_count = min(len(removable), replacement_count)
            removed = rng.choice(removable, size=remove_count, replace=False)
            support.difference_update(int(value) for value in removed)

    pool = ALL_VARIABLES.copy()
    rng.shuffle(pool)
    for value in pool:
        if len(support) >= target_size:
            break
        support.add(int(value))

    if len(support) > target_size:
        removable = np.asarray(sorted(support - mandatory), dtype=np.int16)
        trim_count = min(len(removable), len(support) - target_size)
        if trim_count:
            removed = rng.choice(removable, size=trim_count, replace=False)
            support.difference_update(int(value) for value in removed)

    for color in range(D):
        witness = _mono_matching_variables(rng, support, color)
        support.update(witness)

    if len(support) > target_size:
        protected: set[int] = set()
        for color in range(D):
            protected.update(_mono_matching_variables(rng, support, color))
        removable = np.asarray(sorted(support - protected), dtype=np.int16)
        trim_count = min(len(removable), len(support) - target_size)
        if trim_count:
            removed = rng.choice(removable, size=trim_count, replace=False)
            support.difference_update(int(value) for value in removed)

    return np.asarray(sorted(support), dtype=np.int16)


def active_rows(support: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    active = np.zeros(VARIABLE_COUNT, dtype=bool)
    active[support] = True
    term_is_active = active[TERM_INDICES].all(axis=2)
    term_counts = term_is_active.sum(axis=1)
    rows = np.flatnonzero((term_counts > 0) | (TARGET != 0))
    return rows.astype(np.int32), term_counts.astype(np.int16)


def choose_equations(
    rng: np.random.Generator,
    support: np.ndarray,
    limit: int,
    *,
    preferred_rows: list[int] | np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    rows, term_counts = active_rows(support)
    active_set = {int(row) for row in rows}
    mono_set = {int(row) for row in MONO_ROWS}
    selected = [int(row) for row in MONO_ROWS]

    capacity = max(0, int(limit) - len(selected))
    if preferred_rows is not None and capacity:
        inherited = [
            int(row)
            for row in preferred_rows
            if int(row) in active_set and int(row) not in mono_set
        ]
        rng.shuffle(inherited)
        keep = min(len(inherited), max(1, int(round(capacity * 0.65))))
        selected.extend(inherited[:keep])

    selected_set = set(selected)
    mixed = [
        int(row)
        for row in rows
        if int(row) not in mono_set and int(row) not in selected_set
    ]
    rng.shuffle(mixed)
    mixed.sort(key=lambda row: (int(term_counts[row]), rng.random()))
    selected.extend(mixed[: max(0, int(limit) - len(selected))])
    return np.asarray(selected, dtype=np.int32), term_counts


def evaluate_equations(
    points: np.ndarray, support: np.ndarray, rows: np.ndarray
) -> np.ndarray:
    """Evaluate selected GHZ equations on support-restricted complex points."""
    full = np.zeros((points.shape[0], VARIABLE_COUNT), dtype=np.complex128)
    full[:, support] = points
    gathered = full[:, TERM_INDICES[rows]]
    amplitudes = gathered.prod(axis=3).sum(axis=2)
    return amplitudes - TARGET[rows][None, :]


def sample_points(rng: np.random.Generator, count: int, variables: int) -> np.ndarray:
    real = rng.normal(0.0, 0.7, size=(count, variables))
    imag = rng.normal(0.0, 0.7, size=(count, variables))
    return (real + 1j * imag) / np.sqrt(2.0)


def feature_matrix(
    equations: np.ndarray, points: np.ndarray, multiplier_positions: np.ndarray
) -> np.ndarray:
    basis = np.concatenate(
        [
            np.ones((points.shape[0], 1), dtype=np.complex128),
            points[:, multiplier_positions],
        ],
        axis=1,
    )
    return (equations[:, :, None] * basis[:, None, :]).reshape(points.shape[0], -1)


def _parent_multiplier_variables(parent: dict[str, Any]) -> list[int]:
    support = [int(value) for value in parent.get("support_variables", [])]
    variables = []
    for position in parent.get("multiplier_positions", []):
        pos = int(position)
        if 0 <= pos < len(support):
            variables.append(support[pos])
    return variables


def search_once(
    rng: np.random.Generator,
    shape: SearchShape,
    *,
    parent: dict[str, Any] | None = None,
    search_mode: str = "fresh",
    mutation_fraction: float = 0.25,
) -> dict:
    parent_support = None if parent is None else parent.get("support_variables", [])
    support = support_template(
        rng,
        shape.support_size,
        parent_support=parent_support,
        mutation_fraction=mutation_fraction,
    )
    preferred_rows = None if parent is None else parent.get("equation_rows", [])
    rows, term_counts = choose_equations(
        rng, support, shape.equation_limit, preferred_rows=preferred_rows
    )
    if len(rows) < 6:
        raise RuntimeError("support activates too few GHZ equations")

    multiplier_count = min(shape.multiplier_count, len(support))
    inherited_variables = set(_parent_multiplier_variables(parent or {}))
    inherited_positions = [
        pos for pos, variable in enumerate(support) if int(variable) in inherited_variables
    ]
    rng.shuffle(inherited_positions)
    preserved_count = min(
        len(inherited_positions),
        multiplier_count,
        max(0, int(round(multiplier_count * 0.60))),
    )
    chosen = list(inherited_positions[:preserved_count])
    chosen_set = set(chosen)
    remaining = [pos for pos in range(len(support)) if pos not in chosen_set]
    if multiplier_count > len(chosen):
        extra = rng.choice(
            np.asarray(remaining, dtype=np.int16),
            size=multiplier_count - len(chosen),
            replace=False,
        )
        chosen.extend(int(value) for value in extra)
    multiplier_positions = np.asarray(sorted(chosen), dtype=np.int16)

    feature_count = len(rows) * (1 + multiplier_count)
    train_count = max(shape.train_samples, 2 * feature_count + 32)

    train_points = sample_points(rng, train_count, len(support))
    train_eq = evaluate_equations(train_points, support, rows)
    matrix = feature_matrix(train_eq, train_points, multiplier_positions)
    target = np.ones(train_count, dtype=np.complex128)

    coefficients, _, rank, singular = linalg.lstsq(
        matrix, target, cond=1e-11, lapack_driver="gelsy"
    )
    train_residual = matrix @ coefficients - target

    validation_points = sample_points(rng, shape.validation_samples, len(support))
    validation_eq = evaluate_equations(validation_points, support, rows)
    validation_matrix = feature_matrix(
        validation_eq, validation_points, multiplier_positions
    )
    validation_residual = validation_matrix @ coefficients - 1.0

    train_rms = float(np.sqrt(np.mean(np.abs(train_residual) ** 2)))
    validation_rms = float(np.sqrt(np.mean(np.abs(validation_residual) ** 2)))
    validation_max = float(np.max(np.abs(validation_residual)))
    coefficient_norm = float(np.linalg.norm(coefficients))
    score = validation_rms + 0.15 * validation_max + 1e-8 * coefficient_norm

    parent_support_set = {
        int(value) for value in (parent or {}).get("support_variables", [])
    }
    support_set = {int(value) for value in support}
    support_distance = len(parent_support_set.symmetric_difference(support_set))

    return {
        "certificate_score": score,
        "train_rms": train_rms,
        "validation_rms": validation_rms,
        "validation_max": validation_max,
        "coefficient_norm": coefficient_norm,
        "rank": int(rank),
        "feature_count": int(feature_count),
        "support_size": int(len(support)),
        "support_variables": [int(v) for v in support],
        "equation_rows": [int(v) for v in rows],
        "active_term_counts": [int(term_counts[row]) for row in rows],
        "multiplier_positions": [int(v) for v in multiplier_positions],
        "coefficients": [[float(z.real), float(z.imag)] for z in coefficients],
        "smallest_reported_singular": (
            float(np.min(np.abs(singular)))
            if singular is not None and len(singular)
            else None
        ),
        "certificate_kind": "affine-nullstellensatz-numerical-candidate",
        "scope": "n=6,d=3,restricted-support-family",
        "search_mode": search_mode,
        "parent_candidate_id": None if parent is None else parent.get("candidate_id"),
        "parent_certificate_score": (
            None if parent is None else parent.get("certificate_score")
        ),
        "mutation_fraction": 0.0 if parent is None else float(mutation_fraction),
        "support_distance_from_parent": (
            None if parent is None else int(support_distance)
        ),
        "inherited_equation_count": (
            0
            if parent is None
            else len(
                set(int(v) for v in parent.get("equation_rows", []))
                & set(int(v) for v in rows)
            )
        ),
        "inherited_multiplier_count": int(preserved_count),
    }


def shape_for(job_id: int, worker_id: int, run_index: int) -> SearchShape:
    key = job_id * 11 + worker_id * 5 + run_index
    support_size = 18 + key % 13
    equation_limit = 12 + 4 * (key % 5)
    multiplier_count = 4 + key % 7
    feature_hint = equation_limit * (1 + multiplier_count)
    return SearchShape(
        support_size=support_size,
        equation_limit=equation_limit,
        multiplier_count=multiplier_count,
        train_samples=max(256, 2 * feature_hint + 32),
        validation_samples=320,
    )
