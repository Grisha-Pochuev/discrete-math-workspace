#!/usr/bin/env python3
"""Exact one-variable deletion contrasts for Fourth approach Run 003.

The input is the accepted Run-002 minimized certificate library. Every parent
certificate is reverified over the rationals. Each one-variable deletion is
then classified independently, canonically under S6 x S3, and supplied with a
small exact certificate when a monochromatic target equation becomes -1.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import gzip
import hashlib
from itertools import permutations
import json
from pathlib import Path
from typing import Any, Iterable

N = 6
D = 3
EDGES = tuple((i, j) for i in range(N) for j in range(i + 1, N))
EDGE_INDEX = {edge: index for index, edge in enumerate(EDGES)}
VARIABLE_COUNT = len(EDGES) * D * D
MONO_ROWS = (0, 364, 728)


def _perfect_matchings(vertices: tuple[int, ...]) -> tuple[tuple[tuple[int, int], ...], ...]:
    if not vertices:
        return (tuple(),)
    first = vertices[0]
    result: list[tuple[tuple[int, int], ...]] = []
    for position in range(1, len(vertices)):
        second = vertices[position]
        rest = vertices[1:position] + vertices[position + 1 :]
        edge = (min(first, second), max(first, second))
        for tail in _perfect_matchings(rest):
            result.append((edge,) + tail)
    return tuple(result)


MATCHINGS = _perfect_matchings(tuple(range(N)))


def variable_index(i: int, j: int, a: int, b: int) -> int:
    if i > j:
        i, j, a, b = j, i, b, a
    return EDGE_INDEX[(i, j)] * D * D + a * D + b


def decode_variable(value: int) -> tuple[int, int, int, int]:
    edge_index, color_pair = divmod(int(value), D * D)
    a, b = divmod(color_pair, D)
    i, j = EDGES[edge_index]
    return i, j, a, b


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
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as handle:
        json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")


def stable_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def stable_shard(key: str, shard_count: int) -> int:
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % shard_count


def variable_map(vertex_permutation: tuple[int, ...], color_permutation: tuple[int, ...]) -> bytes:
    mapping = bytearray(VARIABLE_COUNT)
    for value in range(VARIABLE_COUNT):
        i, j, a, b = decode_variable(value)
        mapping[value] = variable_index(
            vertex_permutation[i], vertex_permutation[j],
            color_permutation[a], color_permutation[b],
        )
    return bytes(mapping)


_TRANSFORMATIONS: tuple[bytes, ...] | None = None


def transformations() -> tuple[bytes, ...]:
    global _TRANSFORMATIONS
    if _TRANSFORMATIONS is None:
        _TRANSFORMATIONS = tuple(
            variable_map(vertex, color)
            for vertex in permutations(range(N))
            for color in permutations(range(D))
        )
    return _TRANSFORMATIONS


def canonical_support(support_values: Iterable[int]) -> tuple[int, ...]:
    support = tuple(sorted({int(value) for value in support_values}))
    if any(not 0 <= value < VARIABLE_COUNT for value in support):
        raise ValueError("support contains invalid variable")
    return min(tuple(sorted(mapping[value] for value in support)) for mapping in transformations())


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


def parse_terms(raw_terms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "row": int(term["row"]),
            "feature": tuple(sorted(int(value) for value in term["feature"])),
            "real": Fraction(int(term["real"][0]), int(term["real"][1])),
            "imag": Fraction(int(term["imag"][0]), int(term["imag"][1])),
        }
        for term in raw_terms
    ]


def verify_sparse_certificate(support_values: Iterable[int], terms: list[dict[str, Any]]) -> tuple[bool, str | None]:
    support = set(int(value) for value in support_values)
    totals: dict[tuple[int, ...], tuple[Fraction, Fraction]] = {}
    for term in terms:
        feature = tuple(term["feature"])
        if any(value not in support for value in feature):
            return False, "feature outside support"
        for monomial, integer in equation_terms(int(term["row"]), support).items():
            key = tuple(sorted(monomial + feature))
            old_real, old_imag = totals.get(key, (Fraction(0), Fraction(0)))
            totals[key] = (
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


def target_zero_certificate(support_values: Iterable[int]) -> tuple[int, list[dict[str, Any]]]:
    support = tuple(sorted(set(int(value) for value in support_values)))
    for row in MONO_ROWS:
        polynomial = equation_terms(row, support)
        if polynomial == {tuple(): -1}:
            certificate = [{
                "row": row,
                "feature": tuple(),
                "real": Fraction(-1),
                "imag": Fraction(0),
            }]
            valid, error = verify_sparse_certificate(support, certificate)
            if not valid:
                raise AssertionError(error)
            return row, certificate
    raise ValueError("no target-zero monochromatic equation found")


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


def analyze_shard(source: Path, shard_id: int, shard_count: int) -> dict[str, Any]:
    document = read_gzip_json(source)
    all_records = list(document.get("records", []))
    assigned = [
        record for record in all_records
        if stable_shard(str(record["canonical_support_id"]), shard_count) == shard_id
    ]
    results: list[dict[str, Any]] = []
    rejected_parents = 0
    rejected_children = 0
    for parent in assigned:
        support = tuple(sorted(int(value) for value in parent["minimized_support_variables"]))
        parent_terms = parse_terms(parent["minimized_terms"])
        parent_valid, parent_error = verify_sparse_certificate(support, parent_terms)
        if not parent_valid:
            rejected_parents += 1
            results.append({
                "canonical_support_id": parent["canonical_support_id"],
                "status": "rejected_parent",
                "error": parent_error,
            })
            continue
        parent_canonical = canonical_support(support)
        parent_class_id = stable_hash({"n": N, "d": D, "support": parent_canonical})
        for deleted in support:
            child = tuple(value for value in support if value != deleted)
            child_canonical = canonical_support(child)
            child_class_id = stable_hash({"n": N, "d": D, "support": child_canonical})
            try:
                target_row, certificate = target_zero_certificate(child)
                child_valid, child_error = verify_sparse_certificate(child, certificate)
            except Exception as exc:
                child_valid = False
                child_error = f"{type(exc).__name__}: {exc}"
                target_row = None
                certificate = []
            if not child_valid:
                rejected_children += 1
            results.append({
                "source_canonical_support_id": str(parent["canonical_support_id"]),
                "source_candidate_id": str(parent.get("candidate_id", "")),
                "parent_support": list(support),
                "parent_canonical_support": list(parent_canonical),
                "parent_minimized_class_id": parent_class_id,
                "deleted_variable": int(deleted),
                "deleted_variable_decoded": list(decode_variable(deleted)),
                "child_support": list(child),
                "child_canonical_support": list(child_canonical),
                "child_class_id": child_class_id,
                "classification": "target_zero" if child_valid else "technical_rejection",
                "target_zero_row": target_row,
                "exact_certificate": serialize_terms(certificate),
                "independently_verified": child_valid,
                "verification_error": child_error,
            })
    return {
        "schema_version": 1,
        "task": "stage3_deletion_contrasts",
        "source": str(source),
        "shard_id": shard_id,
        "shard_count": shard_count,
        "complete": True,
        "records": results,
        "metrics": {
            "global_parent_records": len(all_records),
            "assigned_parent_records": len(assigned),
            "deletion_children_tested": sum(1 for record in results if "child_support" in record),
            "target_zero_children": sum(1 for record in results if record.get("classification") == "target_zero"),
            "rejected_parents": rejected_parents,
            "rejected_children": rejected_children,
            "parent_canonical_classes_within_shard": len({record.get("parent_minimized_class_id") for record in results if record.get("parent_minimized_class_id")}),
            "child_canonical_classes_within_shard": len({record.get("child_class_id") for record in results if record.get("child_class_id")}),
        },
    }


def self_test() -> None:
    parent = (0, 81, 126)
    assert canonical_support(parent) == parent
    child = (0, 81)
    assert canonical_support(child) == child
    row, certificate = target_zero_certificate(child)
    assert row in MONO_ROWS
    assert verify_sparse_certificate(child, certificate)[0]
    transformed = (8, 107, 116)
    assert canonical_support(transformed) == parent
    print(json.dumps({"self_test": "ok", "parent": parent, "child": child}))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    parser.add_argument("--shard-id", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.source is None or args.output is None:
        parser.error("--source and --output are required")
    if not 0 <= args.shard_id < args.shard_count:
        parser.error("invalid shard coordinates")
    payload = analyze_shard(args.source, args.shard_id, args.shard_count)
    write_gzip_json(args.output, payload)
    print(json.dumps(payload["metrics"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
