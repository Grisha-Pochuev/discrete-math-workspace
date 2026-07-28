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

import numpy as np
from scipy import linalg

N = 6
D = 3
EDGES = [(i, j) for i in range(N) for j in range(i + 1, N)]
EDGE_INDEX = {edge: k for k, edge in enumerate(EDGES)}
VARIABLE_COUNT = len(EDGES) * D * D


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


def support_template(rng: np.random.Generator, support_size: int) -> np.ndarray:
    """Balanced support containing a monochromatic matching for every color."""
    support: set[int] = set()
    for color in range(D):
        matching = MATCHINGS[int(rng.integers(0, len(MATCHINGS)))]
        for i, j in matching:
            support.add(variable_index(i, j, color, color))

    cross = [
        variable_index(i, j, a, b)
        for i, j in EDGES
        for a in range(D)
        for b in range(D)
        if a != b
    ]
    mono = [
        variable_index(i, j, a, a)
        for i, j in EDGES
        for a in range(D)
    ]
    rng.shuffle(cross)
    rng.shuffle(mono)
    for idx in cross + mono:
        if len(support) >= support_size:
            break
        support.add(int(idx))
    return np.asarray(sorted(support), dtype=np.int16)


def active_rows(support: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    active = np.zeros(VARIABLE_COUNT, dtype=bool)
    active[support] = True
    term_is_active = active[TERM_INDICES].all(axis=2)
    term_counts = term_is_active.sum(axis=1)
    rows = np.flatnonzero((term_counts > 0) | (TARGET != 0))
    return rows.astype(np.int32), term_counts.astype(np.int16)


def choose_equations(
    rng: np.random.Generator, support: np.ndarray, limit: int
) -> tuple[np.ndarray, np.ndarray]:
    rows, term_counts = active_rows(support)
    mono_set = {int(row) for row in MONO_ROWS}
    mono = [int(row) for row in MONO_ROWS]
    mixed = [int(row) for row in rows if int(row) not in mono_set]
    rng.shuffle(mixed)
    mixed.sort(key=lambda row: (int(term_counts[row]), rng.random()))
    selected = mono + mixed[: max(0, limit - len(mono))]
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


def search_once(rng: np.random.Generator, shape: SearchShape) -> dict:
    support = support_template(rng, shape.support_size)
    rows, term_counts = choose_equations(rng, support, shape.equation_limit)
    if len(rows) < 6:
        raise RuntimeError("support activates too few GHZ equations")

    multiplier_count = min(shape.multiplier_count, len(support))
    multiplier_positions = np.sort(
        rng.choice(len(support), size=multiplier_count, replace=False)
    ).astype(np.int16)
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
