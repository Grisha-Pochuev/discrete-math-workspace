#!/usr/bin/env python3
"""Exact time-bounded minimization of restricted n=6,d=3 certificates."""
from __future__ import annotations

from fractions import Fraction
import gzip
import hashlib
import json
import random
import time
from pathlib import Path
from typing import Any, Iterable

N = 6
D = 3
EDGES = tuple((i, j) for i in range(N) for j in range(i + 1, N))
EDGE_INDEX = {edge: index for index, edge in enumerate(EDGES)}
VARIABLE_COUNT = len(EDGES) * D * D


def _perfect_matchings(vertices: tuple[int, ...]) -> tuple[tuple[tuple[int, int], ...], ...]:
    if not vertices:
        return (tuple(),)
    first = vertices[0]
    result: list[tuple[tuple[int, int], ...]] = []
    for position in range(1, len(vertices)):
        second = vertices[position]
        remaining = vertices[1:position] + vertices[position + 1 :]
        edge = (min(first, second), max(first, second))
        for tail in _perfect_matchings(remaining):
            result.append((edge,) + tail)
    return tuple(result)


MATCHINGS = _perfect_matchings(tuple(range(N)))


def variable_index(i: int, j: int, a: int, b: int) -> int:
    if i > j:
        i, j, a, b = j, i, b, a
    return EDGE_INDEX[(i, j)] * D * D + a * D + b


def decode_coloring(row: int) -> tuple[int, ...]:
    values = [0] * N
    row = int(row)
    for position in range(N - 1, -1, -1):
        row, values[position] = divmod(row, D)
    return tuple(values)


def read_gzip_json(path: Path) -> Any:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def write_gzip_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with gzip.open(temporary, "wt", encoding="utf-8", compresslevel=9) as handle:
        json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
    temporary.replace(path)


def _fraction(raw: Any) -> Fraction:
    return Fraction(int(raw[0]), int(raw[1]))


def parse_exact_terms(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    descriptors = candidate["column_descriptors"]
    coefficients = candidate["exact_rational_coefficients"]
    if len(descriptors) != len(coefficients):
        raise ValueError("descriptor/coefficient length mismatch")
    terms: list[dict[str, Any]] = []
    for descriptor, raw in zip(descriptors, coefficients):
        real = _fraction(raw[0])
        imag = _fraction(raw[1])
        if real == 0 and imag == 0:
            continue
        terms.append(
            {
                "row": int(descriptor[0]),
                "feature": tuple(sorted(int(v) for v in descriptor[1])),
                "real": real,
                "imag": imag,
            }
        )
    return terms


def equation_terms(row: int, support: set[int]) -> dict[tuple[int, ...], int]:
    coloring = decode_coloring(row)
    terms: dict[tuple[int, ...], int] = {}
    for matching in MATCHINGS:
        monomial = tuple(
            sorted(variable_index(i, j, coloring[i], coloring[j]) for i, j in matching)
        )
        if all(value in support for value in monomial):
            terms[monomial] = terms.get(monomial, 0) + 1
    if len(set(coloring)) == 1:
        terms[tuple()] = terms.get(tuple(), 0) - 1
    return {key: value for key, value in terms.items() if value}


def column_polynomial(row: int, feature: tuple[int, ...], support: set[int]) -> dict[tuple[int, ...], int]:
    result: dict[tuple[int, ...], int] = {}
    for monomial, coefficient in equation_terms(row, support).items():
        key = tuple(sorted(monomial + feature))
        result[key] = result.get(key, 0) + coefficient
    return {key: value for key, value in result.items() if value}


def verify_sparse_certificate(support_values: Iterable[int], terms: list[dict[str, Any]]) -> tuple[bool, str | None]:
    support = set(int(value) for value in support_values)
    totals: dict[tuple[int, ...], tuple[Fraction, Fraction]] = {}
    for term in terms:
        feature = tuple(term["feature"])
        if any(value not in support for value in feature):
            return False, "feature outside support"
        polynomial = column_polynomial(int(term["row"]), feature, support)
        for monomial, integer in polynomial.items():
            old_real, old_imag = totals.get(monomial, (Fraction(0), Fraction(0)))
            totals[monomial] = (
                old_real + integer * Fraction(term["real"]),
                old_imag + integer * Fraction(term["imag"]),
            )
    constant = totals.pop(tuple(), (Fraction(0), Fraction(0)))
    if constant != (Fraction(1), Fraction(0)):
        return False, f"constant={constant}"
    residual = {key: value for key, value in totals.items() if value != (0, 0)}
    if residual:
        key = min(residual)
        return False, f"residual {key}={residual[key]}"
    return True, None


def solve_descriptors(
    support_values: Iterable[int], descriptors: list[tuple[int, tuple[int, ...]]]
) -> list[dict[str, Any]] | None:
    """Find an exact real rational solution for the selected descriptors."""
    if not descriptors:
        return None
    support = set(int(value) for value in support_values)
    columns = [column_polynomial(row, feature, support) for row, feature in descriptors]
    monomials = sorted({key for column in columns for key in column} | {tuple()})
    rows: list[list[Fraction]] = []
    for monomial in monomials:
        row = [Fraction(column.get(monomial, 0)) for column in columns]
        rhs = Fraction(1 if monomial == tuple() else 0)
        if any(row) or rhs:
            rows.append(row + [rhs])
    width = len(descriptors)
    pivot_row = 0
    pivot_columns: list[int] = []
    for column in range(width):
        pivot = next((r for r in range(pivot_row, len(rows)) if rows[r][column]), None)
        if pivot is None:
            continue
        rows[pivot_row], rows[pivot] = rows[pivot], rows[pivot_row]
        scale = rows[pivot_row][column]
        rows[pivot_row] = [value / scale for value in rows[pivot_row]]
        for r in range(len(rows)):
            if r == pivot_row or not rows[r][column]:
                continue
            factor = rows[r][column]
            rows[r] = [a - factor * b for a, b in zip(rows[r], rows[pivot_row])]
        pivot_columns.append(column)
        pivot_row += 1
        if pivot_row == len(rows):
            break
    for row in rows:
        if not any(row[:width]) and row[width] != 0:
            return None
    solution = [Fraction(0) for _ in range(width)]
    for r, column in enumerate(pivot_columns):
        solution[column] = rows[r][width]
    result = [
        {"row": row, "feature": feature, "real": coefficient, "imag": Fraction(0)}
        for (row, feature), coefficient in zip(descriptors, solution)
        if coefficient != 0
    ]
    valid, _ = verify_sparse_certificate(support, result)
    return result if valid else None


def coefficient_height(terms: list[dict[str, Any]]) -> int:
    height = 0
    for term in terms:
        for value in (term["real"], term["imag"]):
            value = Fraction(value)
            height += abs(value.numerator).bit_length() + value.denominator.bit_length()
    return height


def objective(support: list[int], terms: list[dict[str, Any]]) -> tuple[int, int, int, tuple[int, ...]]:
    return (len(support), len(terms), coefficient_height(terms), tuple(support))


def minimize_once(candidate: dict[str, Any], rng: random.Random) -> tuple[list[int], list[dict[str, Any]]]:
    support = sorted({int(value) for value in candidate["support_variables"]})
    original_terms = parse_exact_terms(candidate)
    descriptors = [(int(term["row"]), tuple(term["feature"])) for term in original_terms]
    solved = solve_descriptors(support, descriptors)
    if solved is None:
        raise ValueError("original exact descriptors could not be independently solved")
    terms = solved

    changed = True
    while changed:
        changed = False
        indices = list(range(len(terms)))
        rng.shuffle(indices)
        for index in indices:
            if index >= len(terms):
                continue
            trial_descriptors = [
                (int(term["row"]), tuple(term["feature"]))
                for position, term in enumerate(terms)
                if position != index
            ]
            replacement = solve_descriptors(support, trial_descriptors)
            if replacement is not None:
                terms = replacement
                changed = True
                break
        if changed:
            continue

        variables = list(support)
        rng.shuffle(variables)
        for variable in variables:
            if any(variable in tuple(term["feature"]) for term in terms):
                continue
            trial_support = [value for value in support if value != variable]
            trial_descriptors = [(int(term["row"]), tuple(term["feature"])) for term in terms]
            replacement = solve_descriptors(trial_support, trial_descriptors)
            if replacement is not None:
                support = trial_support
                terms = replacement
                changed = True
                break
    valid, error = verify_sparse_certificate(support, terms)
    if not valid:
        raise ValueError(f"minimized certificate failed verification: {error}")
    return support, terms


def serialize_terms(terms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "row": int(term["row"]),
            "feature": [int(value) for value in term["feature"]],
            "real": [Fraction(term["real"]).numerator, Fraction(term["real"]).denominator],
            "imag": [Fraction(term["imag"]).numerator, Fraction(term["imag"]).denominator],
        }
        for term in terms
    ]


def stable_shard(key: str, shard_count: int) -> int:
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % shard_count


def process_stage2_shard(
    repo: Path,
    spec: dict[str, Any],
    shard_id: int,
    shard_count: int,
    *,
    seconds: int,
    max_attempts: int,
    checkpoint_path: Path | None = None,
) -> dict[str, Any]:
    source_classes = repo / str(spec["source_canonical_classes"])
    classes_document = json.loads(source_classes.read_text(encoding="utf-8"))
    all_classes = list(classes_document.get("classes", []))
    assigned = [
        item for item in all_classes
        if stable_shard(str(item["canonical_support_id"]), shard_count) == shard_id
    ]

    requested: dict[str, set[str]] = {}
    class_by_candidate: dict[tuple[str, str], dict[str, Any]] = {}
    for item in assigned:
        representative = item.get("representative") or {}
        source_path = str(representative.get("source_path", ""))
        candidate_id = str(representative.get("candidate_id", ""))
        if not source_path or not candidate_id:
            raise ValueError("canonical class has no usable representative")
        requested.setdefault(source_path, set()).add(candidate_id)
        class_by_candidate[(source_path, candidate_id)] = item

    candidates: dict[tuple[str, str], dict[str, Any]] = {}
    for source_path, identifiers in requested.items():
        document = read_gzip_json(repo / source_path)
        for candidate in document.get("candidates", []):
            identifier = str(candidate.get("candidate_id", ""))
            if identifier in identifiers:
                candidates[(source_path, identifier)] = candidate
    if len(candidates) != len(assigned):
        missing = sorted(set(class_by_candidate) - set(candidates))
        raise ValueError(f"missing representatives: {missing[:3]}")

    started = time.time()
    deadline = started + max(60, seconds - 300)
    rng = random.Random(2_000_003 + shard_id)
    records: dict[str, dict[str, Any]] = {}
    attempts = 0

    def checkpoint(complete: bool = False) -> dict[str, Any]:
        payload = {
            "schema_version": 1,
            "task": "stage2_minimize_certificates",
            "shard_id": shard_id,
            "shard_count": shard_count,
            "complete": complete,
            "total_canonical_classes": len(all_classes),
            "assigned_classes": len(assigned),
            "attempts": attempts,
            "records": [records[key] for key in sorted(records)],
            "metrics": {
                "total_canonical_classes": len(all_classes),
                "assigned_classes": len(assigned),
                "classes_attempted": len(records),
                "optimization_attempts": attempts,
                "classes_with_smaller_support": sum(1 for r in records.values() if r["support_removed"] > 0),
                "classes_with_fewer_terms": sum(1 for r in records.values() if r["terms_removed"] > 0),
                "support_variables_removed": sum(r["support_removed"] for r in records.values()),
                "certificate_terms_removed": sum(r["terms_removed"] for r in records.values()),
                "independently_reverified": sum(1 for r in records.values() if r["verified_exact"]),
            },
        }
        if checkpoint_path is not None:
            write_gzip_json(checkpoint_path, payload)
        return payload

    queue = list(assigned)
    while queue and time.time() < deadline:
        item = queue.pop(0)
        representative = item["representative"]
        key_tuple = (str(representative["source_path"]), str(representative["candidate_id"]))
        candidate = candidates[key_tuple]
        support, terms = minimize_once(candidate, rng)
        original_terms = parse_exact_terms(candidate)
        record = {
            "canonical_support_id": str(item["canonical_support_id"]),
            "candidate_id": str(representative["candidate_id"]),
            "source_path": str(representative["source_path"]),
            "source_run_id": representative.get("source_run_id"),
            "original_support_size": len(candidate["support_variables"]),
            "original_nonzero_terms": len(original_terms),
            "minimized_support_variables": support,
            "minimized_terms": serialize_terms(terms),
            "minimized_support_size": len(support),
            "minimized_nonzero_terms": len(terms),
            "support_removed": len(candidate["support_variables"]) - len(support),
            "terms_removed": len(original_terms) - len(terms),
            "coefficient_height": coefficient_height(terms),
            "verified_exact": True,
            "minimality_scope": "greedy deletion plus exact rational re-solving; not a global minimum proof",
            "optimization_attempts": 1,
        }
        records[record["canonical_support_id"]] = record
        attempts += 1
        if attempts % 8 == 0:
            checkpoint(False)
        if max_attempts > 0 and attempts >= max_attempts:
            break

    coverage_complete = len(records) == len(assigned)
    # Use remaining time for randomized restarts over covered classes.
    covered = list(records)
    while coverage_complete and covered and time.time() < deadline and (max_attempts <= 0 or attempts < max_attempts):
        class_id = rng.choice(covered)
        item = next(value for value in assigned if value["canonical_support_id"] == class_id)
        representative = item["representative"]
        key_tuple = (str(representative["source_path"]), str(representative["candidate_id"]))
        candidate = candidates[key_tuple]
        support, terms = minimize_once(candidate, rng)
        current = records[class_id]
        if objective(support, terms) < objective(current["minimized_support_variables"], [
            {"row": t["row"], "feature": tuple(t["feature"]), "real": _fraction(t["real"]), "imag": _fraction(t["imag"])}
            for t in current["minimized_terms"]
        ]):
            current["minimized_support_variables"] = support
            current["minimized_terms"] = serialize_terms(terms)
            current["minimized_support_size"] = len(support)
            current["minimized_nonzero_terms"] = len(terms)
            current["support_removed"] = current["original_support_size"] - len(support)
            current["terms_removed"] = current["original_nonzero_terms"] - len(terms)
            current["coefficient_height"] = coefficient_height(terms)
        current["optimization_attempts"] += 1
        attempts += 1
        if attempts % 8 == 0:
            checkpoint(False)

    return checkpoint(coverage_complete)
