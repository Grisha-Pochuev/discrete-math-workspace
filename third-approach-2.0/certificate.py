#!/usr/bin/env python3
"""Coefficient-space search for restricted Krenn--Gu proof certificates.

The engine searches identities 1 = sum_j c_j m_j F_{r_j} for n=6,d=3,
where F_r are support-restricted GHZ equations and m_j are multiplier
monomials of configurable degree. Scores are computed from polynomial
coefficients, not random point samples. A numerical zero is only a lead;
`exact_verified=True` means rational reconstruction passed an exact check for
that restricted support system.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from fractions import Fraction
import hashlib
from itertools import product
import json
from typing import Any, Iterable

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import lsqr

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
    result: list[tuple[tuple[int, int], ...]] = []
    for pos in range(1, len(vertices)):
        second = vertices[pos]
        rest = vertices[1:pos] + vertices[pos + 1 :]
        edge = (min(first, second), max(first, second))
        for tail in _perfect_matchings(rest):
            result.append((edge,) + tail)
    return result


MATCHINGS = _perfect_matchings(tuple(range(N)))
COLORINGS = np.asarray(list(product(range(D), repeat=N)), dtype=np.int8)
MONO_ROWS = np.asarray(
    [sum(c * (D ** (N - 1 - k)) for k in range(N)) for c in range(D)],
    dtype=np.int32,
)
TARGET = np.zeros(D**N, dtype=np.int8)
TARGET[MONO_ROWS] = 1


def variable_index(i: int, j: int, a: int, b: int) -> int:
    if i > j:
        i, j, a, b = j, i, b, a
    return EDGE_INDEX[(i, j)] * D * D + a * D + b


TERM_INDICES = np.empty((D**N, len(MATCHINGS), N // 2), dtype=np.int16)
for row, colouring in enumerate(COLORINGS):
    for mid, matching in enumerate(MATCHINGS):
        TERM_INDICES[row, mid] = [
            variable_index(i, j, int(colouring[i]), int(colouring[j]))
            for i, j in matching
        ]


@dataclass(frozen=True)
class SearchShape:
    support_size: int
    equation_limit: int
    linear_features: int
    quadratic_features: int
    cubic_features: int
    max_iterations: int = 2500

    @property
    def max_multiplier_degree(self) -> int:
        if self.cubic_features:
            return 3
        if self.quadratic_features:
            return 2
        return 1


def _hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:20]


def _mono_matching_variables(
    rng: np.random.Generator, support: set[int], colour: int
) -> set[int]:
    active = []
    for matching in MATCHINGS:
        variables = {variable_index(i, j, colour, colour) for i, j in matching}
        if variables.issubset(support):
            active.append(variables)
    if active:
        return set(active[int(rng.integers(0, len(active)))])
    matching = MATCHINGS[int(rng.integers(0, len(MATCHINGS)))]
    return {variable_index(i, j, colour, colour) for i, j in matching}


def support_template(
    rng: np.random.Generator,
    support_size: int,
    *,
    parent_support: Iterable[int] | None = None,
    mutation_fraction: float = 0.25,
) -> np.ndarray:
    target_size = int(np.clip(support_size, 9, VARIABLE_COUNT))
    support = {
        int(value)
        for value in (parent_support or [])
        if 0 <= int(value) < VARIABLE_COUNT
    }
    mandatory: set[int] = set()
    for colour in range(D):
        witness = _mono_matching_variables(rng, support, colour)
        support.update(witness)
        mandatory.update(witness)

    if parent_support is not None and support:
        replacement_count = max(
            1, int(round(target_size * float(np.clip(mutation_fraction, 0.01, 0.90))))
        )
        removable = np.asarray(sorted(support - mandatory), dtype=np.int16)
        if len(removable):
            removed = rng.choice(
                removable, size=min(len(removable), replacement_count), replace=False
            )
            support.difference_update(int(value) for value in removed)

    pool = ALL_VARIABLES.copy()
    rng.shuffle(pool)
    for value in pool:
        if len(support) >= target_size:
            break
        support.add(int(value))

    if len(support) > target_size:
        removable = np.asarray(sorted(support - mandatory), dtype=np.int16)
        trim = min(len(removable), len(support) - target_size)
        if trim:
            removed = rng.choice(removable, size=trim, replace=False)
            support.difference_update(int(value) for value in removed)

    for colour in range(D):
        support.update(_mono_matching_variables(rng, support, colour))
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
    preferred_rows: Iterable[int] | None = None,
    retention: float = 0.70,
) -> tuple[np.ndarray, np.ndarray]:
    rows, term_counts = active_rows(support)
    active_set = {int(row) for row in rows}
    selected = [int(row) for row in MONO_ROWS]
    capacity = max(0, int(limit) - len(selected))

    inherited = []
    if preferred_rows is not None:
        inherited = [
            int(row)
            for row in preferred_rows
            if int(row) in active_set and int(row) not in set(MONO_ROWS.tolist())
        ]
        rng.shuffle(inherited)
        selected.extend(inherited[: min(len(inherited), int(capacity * retention))])

    selected_set = set(selected)
    mixed = [int(row) for row in rows if int(row) not in selected_set]
    rng.shuffle(mixed)
    mixed.sort(key=lambda row: (int(term_counts[row]), rng.random()))
    selected.extend(mixed[: max(0, int(limit) - len(selected))])
    return np.asarray(selected, dtype=np.int32), term_counts


def _random_monomials(
    rng: np.random.Generator,
    support: np.ndarray,
    degree: int,
    count: int,
    existing: set[tuple[int, ...]],
) -> list[tuple[int, ...]]:
    if count <= 0:
        return []
    result: list[tuple[int, ...]] = []
    attempts = 0
    max_attempts = max(100, count * 40)
    values = [int(v) for v in support]
    while len(result) < count and attempts < max_attempts:
        monomial = tuple(sorted(int(v) for v in rng.choice(values, size=degree, replace=True)))
        attempts += 1
        if monomial not in existing:
            existing.add(monomial)
            result.append(monomial)
    return result


def choose_features(
    rng: np.random.Generator,
    support: np.ndarray,
    shape: SearchShape,
    *,
    parent_features: Iterable[Iterable[int]] | None = None,
    retention: float = 0.65,
) -> list[tuple[int, ...]]:
    support_set = {int(v) for v in support}
    features: list[tuple[int, ...]] = [tuple()]
    existing = {tuple()}

    inherited = []
    for raw in parent_features or []:
        feature = tuple(sorted(int(v) for v in raw))
        if (
            1 <= len(feature) <= shape.max_multiplier_degree
            and all(v in support_set for v in feature)
            and feature not in existing
        ):
            inherited.append(feature)
    rng.shuffle(inherited)
    inherited_limit = int(
        retention
        * (shape.linear_features + shape.quadratic_features + shape.cubic_features)
    )
    for feature in inherited[:inherited_limit]:
        features.append(feature)
        existing.add(feature)

    targets = {
        1: shape.linear_features,
        2: shape.quadratic_features,
        3: shape.cubic_features,
    }
    for degree, target in targets.items():
        current = sum(1 for feature in features if len(feature) == degree)
        features.extend(
            _random_monomials(rng, support, degree, max(0, target - current), existing)
        )
    return sorted(features, key=lambda item: (len(item), item))


def equation_terms(row: int, support_set: set[int]) -> dict[tuple[int, ...], int]:
    terms: dict[tuple[int, ...], int] = {}
    for matching_vars in TERM_INDICES[row]:
        monomial = tuple(sorted(int(v) for v in matching_vars))
        if all(v in support_set for v in monomial):
            terms[monomial] = terms.get(monomial, 0) + 1
    if int(TARGET[row]):
        terms[tuple()] = terms.get(tuple(), 0) - int(TARGET[row])
    return {key: value for key, value in terms.items() if value}


def coefficient_system(
    support: np.ndarray,
    rows: np.ndarray,
    features: list[tuple[int, ...]],
) -> tuple[sparse.csr_matrix, np.ndarray, list[tuple[int, ...]], list[tuple[int, tuple[int, ...]]]]:
    support_set = {int(v) for v in support}
    columns: list[dict[tuple[int, ...], int]] = []
    descriptors: list[tuple[int, tuple[int, ...]]] = []
    monomial_set: set[tuple[int, ...]] = {tuple()}

    for row in rows:
        base = equation_terms(int(row), support_set)
        for feature in features:
            column: dict[tuple[int, ...], int] = {}
            for monomial, coeff in base.items():
                key = tuple(sorted(monomial + feature))
                column[key] = column.get(key, 0) + coeff
                monomial_set.add(key)
            columns.append(column)
            descriptors.append((int(row), feature))

    monomials = sorted(monomial_set, key=lambda item: (len(item), item))
    row_index = {monomial: idx for idx, monomial in enumerate(monomials)}
    data: list[float] = []
    row_ids: list[int] = []
    col_ids: list[int] = []
    for col, polynomial in enumerate(columns):
        for monomial, coeff in polynomial.items():
            row_ids.append(row_index[monomial])
            col_ids.append(col)
            data.append(float(coeff))
    matrix = sparse.coo_matrix(
        (data, (row_ids, col_ids)), shape=(len(monomials), len(columns)), dtype=float
    ).tocsr()
    target = np.zeros(len(monomials), dtype=float)
    target[row_index[tuple()]] = 1.0
    return matrix, target, monomials, descriptors


def _fraction_pair(value: complex, denominator_limit: int) -> tuple[Fraction, Fraction]:
    return (
        Fraction(float(value.real)).limit_denominator(denominator_limit),
        Fraction(float(value.imag)).limit_denominator(denominator_limit),
    )


def exact_rational_verification(
    matrix: sparse.csr_matrix,
    target: np.ndarray,
    coefficients: np.ndarray,
    *,
    denominator_limit: int = 100_000,
) -> tuple[bool, list[list[list[int]]] | None]:
    rational = [_fraction_pair(complex(value), denominator_limit) for value in coefficients]
    totals = [(Fraction(0), Fraction(0)) for _ in range(matrix.shape[0])]
    coo = matrix.tocoo()
    for row, col, raw in zip(coo.row, coo.col, coo.data):
        real, imag = rational[int(col)]
        coeff = Fraction(int(round(float(raw))))
        old_real, old_imag = totals[int(row)]
        totals[int(row)] = (old_real + coeff * real, old_imag + coeff * imag)
    for idx, (real, imag) in enumerate(totals):
        expected = Fraction(int(round(float(target[idx]))))
        if real != expected or imag != 0:
            return False, None
    serialised = [
        [[value[0].numerator, value[0].denominator], [value[1].numerator, value[1].denominator]]
        for value in rational
    ]
    return True, serialised


def search_once(
    rng: np.random.Generator,
    shape: SearchShape,
    *,
    parent: dict[str, Any] | None = None,
    lane: str = "fresh",
    support_mutation: float = 0.25,
    equation_retention: float = 0.70,
    feature_retention: float = 0.65,
) -> dict[str, Any]:
    support = support_template(
        rng,
        shape.support_size,
        parent_support=None if parent is None else parent.get("support_variables", []),
        mutation_fraction=support_mutation,
    )
    rows, term_counts = choose_equations(
        rng,
        support,
        shape.equation_limit,
        preferred_rows=None if parent is None else parent.get("equation_rows", []),
        retention=equation_retention,
    )
    if len(rows) < 6:
        raise RuntimeError("support activates too few equations")
    features = choose_features(
        rng,
        support,
        shape,
        parent_features=None if parent is None else parent.get("multiplier_features", []),
        retention=feature_retention,
    )
    matrix, target, monomials, descriptors = coefficient_system(support, rows, features)
    if matrix.shape[1] == 0:
        raise RuntimeError("empty certificate feature matrix")

    solution = lsqr(
        matrix,
        target,
        atol=1e-12,
        btol=1e-12,
        iter_lim=shape.max_iterations,
        show=False,
    )
    coefficients = np.asarray(solution[0], dtype=float).astype(np.complex128)
    residual = matrix @ coefficients.real - target
    residual_abs = np.abs(residual)
    rms = float(np.sqrt(np.mean(residual_abs**2)))
    maximum = float(np.max(residual_abs))
    coefficient_norm = float(np.linalg.norm(coefficients))
    score = rms + 0.20 * maximum + 1e-12 * coefficient_norm

    exact_verified = False
    exact_coefficients = None
    if maximum < 1e-9:
        exact_verified, exact_coefficients = exact_rational_verification(
            matrix, target, coefficients
        )

    parent_support = set(int(v) for v in (parent or {}).get("support_variables", []))
    support_set = set(int(v) for v in support)
    feature_degree_counts = {
        str(degree): sum(1 for feature in features if len(feature) == degree)
        for degree in range(4)
    }
    support_fingerprint = _hash(sorted(support_set))
    basin_fingerprint = _hash(
        {
            "support": sorted(support_set),
            "rows": [int(v) for v in rows],
            "degree_counts": feature_degree_counts,
        }
    )

    return {
        "certificate_score": score,
        "coefficient_rms": rms,
        "coefficient_max": maximum,
        "coefficient_norm": coefficient_norm,
        "lsqr_stop_code": int(solution[1]),
        "lsqr_iterations": int(solution[2]),
        "matrix_rows": int(matrix.shape[0]),
        "matrix_columns": int(matrix.shape[1]),
        "support_size": int(len(support)),
        "support_variables": [int(v) for v in support],
        "equation_rows": [int(v) for v in rows],
        "active_term_counts": [int(term_counts[row]) for row in rows],
        "multiplier_features": [[int(v) for v in feature] for feature in features],
        "feature_degree_counts": feature_degree_counts,
        "column_descriptors": [
            [int(row), [int(v) for v in feature]] for row, feature in descriptors
        ],
        "coefficients": [[float(z.real), float(z.imag)] for z in coefficients],
        "exact_verified": exact_verified,
        "exact_rational_coefficients": exact_coefficients,
        "certificate_kind": "coefficient-space-nullstellensatz-candidate",
        "scope": "n=6,d=3,support-restricted-system",
        "lane": lane,
        "max_multiplier_degree": shape.max_multiplier_degree,
        "support_fingerprint": support_fingerprint,
        "basin_fingerprint": basin_fingerprint,
        "parent_candidate_id": None if parent is None else parent.get("candidate_id"),
        "parent_certificate_score": None if parent is None else parent.get("certificate_score"),
        "support_distance_from_parent": None if parent is None else len(parent_support ^ support_set),
        "inherited_equation_count": 0 if parent is None else len(set(parent.get("equation_rows", [])) & set(int(v) for v in rows)),
        "inherited_feature_count": 0 if parent is None else len({tuple(v) for v in parent.get("multiplier_features", [])} & set(features)),
        "polynomial_monomial_count": len(monomials),
    }


def shape_for(
    job_id: int,
    worker_id: int,
    run_index: int,
    profile: str,
    lane: str,
) -> SearchShape:
    key = job_id * 17 + worker_id * 7 + run_index * 3
    if lane == "degree_expand" or profile == "degree_expand":
        return SearchShape(24 + key % 20, 18 + 2 * (key % 10), 8 + key % 7, 8 + key % 11, 2 + key % 7, 4000)
    if lane == "support_escape" or profile == "support_escape":
        return SearchShape(40 + key % 35, 18 + 2 * (key % 9), 8 + key % 8, 6 + key % 10, key % 5, 3500)
    if lane == "contrast_focus" or profile == "contrast_focus":
        return SearchShape(18 + key % 20, 16 + 2 * (key % 8), 7 + key % 8, 4 + key % 8, key % 3, 3000)
    if profile == "multi_basin":
        return SearchShape(20 + key % 35, 14 + 2 * (key % 12), 6 + key % 10, 3 + key % 11, key % 4, 3000)
    return SearchShape(18 + key % 24, 14 + 2 * (key % 10), 6 + key % 9, 2 + key % 8, key % 3, 2800)


def self_test() -> None:
    rng = np.random.default_rng(12345)
    shape = SearchShape(18, 10, 3, 2, 0, 300)
    first = search_once(rng, shape)
    assert first["matrix_columns"] > 0
    assert first["matrix_rows"] > 0
    assert np.isfinite(first["certificate_score"])
    second = search_once(rng, shape, parent=first, lane="contrast_focus", support_mutation=0.08)
    assert second["parent_candidate_id"] is None
    json.dumps(second)
    print(json.dumps({"self_test": "ok", "scores": [first["certificate_score"], second["certificate_score"]]}))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    parser.error("choose --self-test")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
