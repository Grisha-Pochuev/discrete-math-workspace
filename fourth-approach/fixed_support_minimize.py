#!/usr/bin/env python3
"""Time-bounded exact certificate minimization with the support held fixed.

Run 002 changed the support and therefore collapsed to unrelated target-zero
subsystems. This module keeps every original support exactly unchanged and
only removes/re-solves certificate descriptors. The result remains a
certificate for the same support-restricted n=6,d=3 system.
"""
from __future__ import annotations

import argparse
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
MONO_ROWS = (0, 364, 728)


def _perfect_matchings(vertices: tuple[int, ...]) -> tuple[tuple[tuple[int, int], ...], ...]:
    if not vertices:
        return (tuple(),)
    first = vertices[0]
    result: list[tuple[tuple[int, int], ...]] = []
    for pos in range(1, len(vertices)):
        second = vertices[pos]
        rest = vertices[1:pos] + vertices[pos + 1 :]
        edge = (min(first, second), max(first, second))
        for tail in _perfect_matchings(rest):
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
        terms.append({
            "row": int(descriptor[0]),
            "feature": tuple(sorted(int(v) for v in descriptor[1])),
            "real": real,
            "imag": imag,
        })
    return terms


def equation_terms(row: int, support_values: Iterable[int]) -> dict[tuple[int, ...], int]:
    support = set(int(value) for value in support_values)
    coloring = decode_coloring(row)
    terms: dict[tuple[int, ...], int] = {}
    for matching in MATCHINGS:
        monomial = tuple(sorted(variable_index(i, j, coloring[i], coloring[j]) for i, j in matching))
        if all(value in support for value in monomial):
            terms[monomial] = terms.get(monomial, 0) + 1
    if len(set(coloring)) == 1:
        terms[tuple()] = terms.get(tuple(), 0) - 1
    return {key: value for key, value in terms.items() if value}


def column_polynomial(row: int, feature: tuple[int, ...], support_values: Iterable[int]) -> dict[tuple[int, ...], int]:
    result: dict[tuple[int, ...], int] = {}
    for monomial, coefficient in equation_terms(row, support_values).items():
        key = tuple(sorted(monomial + feature))
        result[key] = result.get(key, 0) + coefficient
    return {key: value for key, value in result.items() if value}


def verify_sparse_certificate(support_values: Iterable[int], terms: list[dict[str, Any]]) -> tuple[bool, str | None]:
    support = tuple(sorted(set(int(value) for value in support_values)))
    totals: dict[tuple[int, ...], tuple[Fraction, Fraction]] = {}
    for term in terms:
        feature = tuple(term["feature"])
        if any(value not in support for value in feature):
            return False, "feature outside fixed support"
        for monomial, integer in column_polynomial(int(term["row"]), feature, support).items():
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
    if not descriptors:
        return None
    support = tuple(sorted(set(int(value) for value in support_values)))
    columns = [column_polynomial(row, feature, support) for row, feature in descriptors]
    monomials = sorted({key for column in columns for key in column} | {tuple()})
    rows: list[list[Fraction]] = []
    for monomial in monomials:
        values = [Fraction(column.get(monomial, 0)) for column in columns]
        rhs = Fraction(1 if monomial == tuple() else 0)
        if any(values) or rhs:
            rows.append(values + [rhs])
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
    terms = [
        {"row": row, "feature": feature, "real": coefficient, "imag": Fraction(0)}
        for (row, feature), coefficient in zip(descriptors, solution)
        if coefficient != 0
    ]
    valid, _ = verify_sparse_certificate(support, terms)
    return terms if valid else None


def coefficient_height(terms: list[dict[str, Any]]) -> int:
    result = 0
    for term in terms:
        for value in (term["real"], term["imag"]):
            value = Fraction(value)
            result += abs(value.numerator).bit_length() + value.denominator.bit_length()
    return result


def objective(terms: list[dict[str, Any]]) -> tuple[int, int, tuple[tuple[int, tuple[int, ...]], ...]]:
    descriptors = tuple(sorted((int(term["row"]), tuple(term["feature"])) for term in terms))
    return len(terms), coefficient_height(terms), descriptors


def mono_matching_counts(support_values: Iterable[int]) -> list[int]:
    support = set(int(value) for value in support_values)
    counts = []
    for row in MONO_ROWS:
        polynomial = equation_terms(row, support)
        counts.append(sum(1 for monomial in polynomial if monomial))
    return counts


def minimize_fixed_support(candidate: dict[str, Any], rng: random.Random) -> list[dict[str, Any]]:
    support = tuple(sorted(set(int(value) for value in candidate["support_variables"])))
    original = parse_exact_terms(candidate)
    valid, error = verify_sparse_certificate(support, original)
    if not valid:
        raise ValueError(f"serialized exact certificate failed: {error}")
    descriptors = [(int(term["row"]), tuple(term["feature"])) for term in original]
    solved = solve_descriptors(support, descriptors)
    if solved is None:
        raise ValueError("original descriptors could not be independently re-solved")
    terms = solved
    changed = True
    while changed:
        changed = False
        order = list(range(len(terms)))
        rng.shuffle(order)
        for index in order:
            if index >= len(terms):
                continue
            trial = [
                (int(term["row"]), tuple(term["feature"]))
                for position, term in enumerate(terms)
                if position != index
            ]
            replacement = solve_descriptors(support, trial)
            if replacement is not None:
                terms = replacement
                changed = True
                break
    valid, error = verify_sparse_certificate(support, terms)
    if not valid:
        raise ValueError(f"fixed-support minimum failed: {error}")
    return terms


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


def process_shard(
    repo: Path,
    source_index: Path,
    shard_id: int,
    shard_count: int,
    *,
    seconds: int,
    max_attempts: int,
    checkpoint_path: Path,
) -> dict[str, Any]:
    index_document = read_gzip_json(source_index)
    all_index_records = list(index_document.get("records", []))
    assigned_index = [
        item for item in all_index_records
        if stable_shard(str(item["canonical_support_id"]), shard_count) == shard_id
    ]
    requested: dict[str, set[str]] = {}
    for item in assigned_index:
        requested.setdefault(str(item["source_path"]), set()).add(str(item["candidate_id"]))
    candidates: dict[tuple[str, str], dict[str, Any]] = {}
    for source_path, identifiers in requested.items():
        document = read_gzip_json(repo / source_path)
        for candidate in document.get("candidates", []):
            identifier = str(candidate.get("candidate_id", ""))
            if identifier in identifiers:
                candidates[(source_path, identifier)] = candidate
    if len(candidates) != len(assigned_index):
        missing = [
            (str(item["source_path"]), str(item["candidate_id"]))
            for item in assigned_index
            if (str(item["source_path"]), str(item["candidate_id"])) not in candidates
        ]
        raise ValueError(f"missing source candidates: {missing[:3]}")

    started = time.time()
    deadline = started + max(60, seconds - 300)
    rng = random.Random(4_000_007 + shard_id)
    records: dict[str, dict[str, Any]] = {}
    attempts = 0

    def checkpoint(complete: bool) -> dict[str, Any]:
        payload = {
            "schema_version": 1,
            "task": "stage4_fixed_support_certificate_minimization",
            "shard_id": shard_id,
            "shard_count": shard_count,
            "complete": complete,
            "global_source_records": len(all_index_records),
            "assigned_records": len(assigned_index),
            "attempts": attempts,
            "records": [records[key] for key in sorted(records)],
            "metrics": {
                "global_source_records": len(all_index_records),
                "assigned_records": len(assigned_index),
                "covered_records": len(records),
                "optimization_attempts": attempts,
                "terms_removed": sum(record["terms_removed"] for record in records.values()),
                "certificates_improved": sum(record["terms_removed"] > 0 for record in records.values()),
                "independently_reverified": sum(record["verified_exact"] for record in records.values()),
                "all_three_monochromatic_targets_present": sum(all(count > 0 for count in record["mono_matching_counts"]) for record in records.values()),
            },
        }
        write_gzip_json(checkpoint_path, payload)
        return payload

    queue = list(assigned_index)
    while queue and time.time() < deadline:
        item = queue.pop(0)
        key = (str(item["source_path"]), str(item["candidate_id"]))
        candidate = candidates[key]
        support = tuple(sorted(int(value) for value in candidate["support_variables"]))
        counts = mono_matching_counts(support)
        if not all(count > 0 for count in counts):
            raise ValueError(f"source support lacks a monochromatic target matching: {key} {counts}")
        original = parse_exact_terms(candidate)
        terms = minimize_fixed_support(candidate, rng)
        records[str(item["canonical_support_id"])] = {
            "canonical_support_id": str(item["canonical_support_id"]),
            "candidate_id": str(item["candidate_id"]),
            "source_path": str(item["source_path"]),
            "source_run_id": item.get("source_run_id"),
            "fixed_support_variables": list(support),
            "fixed_support_size": len(support),
            "mono_matching_counts": counts,
            "original_nonzero_terms": len(original),
            "minimized_nonzero_terms": len(terms),
            "terms_removed": len(original) - len(terms),
            "coefficient_height": coefficient_height(terms),
            "minimized_terms": serialize_terms(terms),
            "verified_exact": True,
            "support_unchanged": True,
            "minimality_scope": "randomized greedy descriptor deletion with exact rational re-solving on the unchanged original support",
            "optimization_attempts": 1,
        }
        attempts += 1
        if attempts % 8 == 0:
            checkpoint(False)
        if max_attempts > 0 and attempts >= max_attempts:
            break

    coverage_complete = len(records) == len(assigned_index)
    covered = list(records)
    while coverage_complete and covered and time.time() < deadline and (max_attempts <= 0 or attempts < max_attempts):
        class_id = rng.choice(covered)
        item = next(value for value in assigned_index if str(value["canonical_support_id"]) == class_id)
        key = (str(item["source_path"]), str(item["candidate_id"]))
        candidate = candidates[key]
        terms = minimize_fixed_support(candidate, rng)
        current = records[class_id]
        current_terms = [
            {
                "row": int(term["row"]),
                "feature": tuple(term["feature"]),
                "real": _fraction(term["real"]),
                "imag": _fraction(term["imag"]),
            }
            for term in current["minimized_terms"]
        ]
        if objective(terms) < objective(current_terms):
            current["minimized_terms"] = serialize_terms(terms)
            current["minimized_nonzero_terms"] = len(terms)
            current["terms_removed"] = current["original_nonzero_terms"] - len(terms)
            current["coefficient_height"] = coefficient_height(terms)
        current["optimization_attempts"] += 1
        attempts += 1
        if attempts % 8 == 0:
            checkpoint(False)
    return checkpoint(coverage_complete)


def self_test(candidate_path: Path) -> None:
    candidate = read_gzip_json(candidate_path)
    rng = random.Random(12345)
    support = tuple(candidate["support_variables"])
    before = parse_exact_terms(candidate)
    after = minimize_fixed_support(candidate, rng)
    assert tuple(sorted(support)) == tuple(sorted(candidate["support_variables"]))
    assert verify_sparse_certificate(support, after)[0]
    assert all(value > 0 for value in mono_matching_counts(support))
    print(json.dumps({
        "self_test": "ok",
        "candidate_id": candidate.get("candidate_id"),
        "support_size": len(support),
        "terms_before": len(before),
        "terms_after": len(after),
    }))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--source-index", type=Path)
    parser.add_argument("--shard-id", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--seconds", type=int, default=900)
    parser.add_argument("--max-attempts", type=int, default=0)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test-candidate", type=Path)
    args = parser.parse_args()
    if args.self_test_candidate is not None:
        self_test(args.self_test_candidate)
        return 0
    if args.source_index is None or args.output is None:
        parser.error("--source-index and --output are required")
    payload = process_shard(
        args.repo.resolve(), args.source_index.resolve(), args.shard_id, args.shard_count,
        seconds=args.seconds, max_attempts=args.max_attempts, checkpoint_path=args.output.resolve(),
    )
    print(json.dumps(payload["metrics"], indent=2, sort_keys=True))
    return 0 if payload["complete"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
