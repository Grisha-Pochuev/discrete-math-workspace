#!/usr/bin/env python3
"""Independent exact verification and symmetry canonicalization for Fourth approach.

This module deliberately does not import the Third approach certificate engine.  It
reconstructs the restricted n=6,d=3 polynomial identity from the serialized
support, equation rows, multiplier features, descriptors, and rational
coefficients.  Canonical support classes are computed under all vertex
permutations and one global permutation of the three colors.
"""
from __future__ import annotations

from fractions import Fraction
import gzip
import hashlib
from itertools import permutations
import json
from pathlib import Path
import time
from typing import Any, Iterable

N = 6
D = 3
EDGES = tuple((i, j) for i in range(N) for j in range(i + 1, N))
EDGE_INDEX = {edge: index for index, edge in enumerate(EDGES)}
VARIABLE_COUNT = len(EDGES) * D * D
COLORING_COUNT = D ** N


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
VERTEX_PERMUTATIONS = tuple(permutations(range(N)))
COLOR_PERMUTATIONS = tuple(permutations(range(D)))


def variable_index(i: int, j: int, a: int, b: int) -> int:
    if i > j:
        i, j, a, b = j, i, b, a
    return EDGE_INDEX[(i, j)] * D * D + a * D + b


def decode_variable(value: int) -> tuple[int, int, int, int]:
    value = int(value)
    if not 0 <= value < VARIABLE_COUNT:
        raise ValueError(f"variable index out of range: {value}")
    edge_index, color_pair = divmod(value, D * D)
    a, b = divmod(color_pair, D)
    i, j = EDGES[edge_index]
    return i, j, a, b


def decode_coloring(row: int) -> tuple[int, ...]:
    row = int(row)
    if not 0 <= row < COLORING_COUNT:
        raise ValueError(f"equation row out of range: {row}")
    values = [0] * N
    for position in range(N - 1, -1, -1):
        row, values[position] = divmod(row, D)
    return tuple(values)


def encode_coloring(colors: Iterable[int]) -> int:
    result = 0
    values = tuple(int(value) for value in colors)
    if len(values) != N or any(not 0 <= value < D for value in values):
        raise ValueError("invalid coloring")
    for value in values:
        result = result * D + value
    return result


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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


def _variable_map(vertex_permutation: tuple[int, ...], color_permutation: tuple[int, ...]) -> bytes:
    mapping = bytearray(VARIABLE_COUNT)
    for value in range(VARIABLE_COUNT):
        i, j, a, b = decode_variable(value)
        ni, nj = vertex_permutation[i], vertex_permutation[j]
        na, nb = color_permutation[a], color_permutation[b]
        mapping[value] = variable_index(ni, nj, na, nb)
    return bytes(mapping)


def all_transformations() -> tuple[tuple[tuple[int, ...], tuple[int, ...], bytes], ...]:
    return tuple(
        (vertex, color, _variable_map(vertex, color))
        for vertex in VERTEX_PERMUTATIONS
        for color in COLOR_PERMUTATIONS
    )


_TRANSFORMATIONS: tuple[tuple[tuple[int, ...], tuple[int, ...], bytes], ...] | None = None


def transformations() -> tuple[tuple[tuple[int, ...], tuple[int, ...], bytes], ...]:
    global _TRANSFORMATIONS
    if _TRANSFORMATIONS is None:
        _TRANSFORMATIONS = all_transformations()
    return _TRANSFORMATIONS


def transform_coloring(
    row: int,
    vertex_permutation: tuple[int, ...],
    color_permutation: tuple[int, ...],
) -> int:
    old = decode_coloring(row)
    new = [0] * N
    for old_vertex, old_color in enumerate(old):
        new[vertex_permutation[old_vertex]] = color_permutation[old_color]
    return encode_coloring(new)


def canonical_support(
    support_variables: Iterable[int],
) -> tuple[tuple[int, ...], list[tuple[tuple[int, ...], tuple[int, ...], bytes]]]:
    support = tuple(sorted({int(value) for value in support_variables}))
    if any(not 0 <= value < VARIABLE_COUNT for value in support):
        raise ValueError("support contains an invalid variable")
    best: tuple[int, ...] | None = None
    ties: list[tuple[tuple[int, ...], tuple[int, ...], bytes]] = []
    for vertex, color, mapping in transformations():
        transformed = tuple(sorted(mapping[value] for value in support))
        if best is None or transformed < best:
            best = transformed
            ties = [(vertex, color, mapping)]
        elif transformed == best:
            ties.append((vertex, color, mapping))
    assert best is not None
    return best, ties


def _fraction(raw: Any) -> Fraction:
    if not isinstance(raw, list) or len(raw) != 2:
        raise ValueError("rational component must be [numerator, denominator]")
    numerator, denominator = int(raw[0]), int(raw[1])
    if denominator == 0:
        raise ValueError("zero denominator")
    return Fraction(numerator, denominator)


def parse_exact_coefficients(candidate: dict[str, Any]) -> list[tuple[Fraction, Fraction]]:
    raw = candidate.get("exact_rational_coefficients")
    if not isinstance(raw, list):
        raise ValueError("missing exact_rational_coefficients")
    parsed: list[tuple[Fraction, Fraction]] = []
    for pair in raw:
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError("complex rational coefficient must have real and imaginary parts")
        parsed.append((_fraction(pair[0]), _fraction(pair[1])))
    return parsed


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
    return {monomial: coefficient for monomial, coefficient in terms.items() if coefficient}


def independent_exact_verification(candidate: dict[str, Any]) -> tuple[bool, str | None, dict[str, int]]:
    try:
        support_values = [int(value) for value in candidate["support_variables"]]
        if len(support_values) != len(set(support_values)):
            raise ValueError("support variables are not unique")
        support = set(support_values)
        rows = [int(value) for value in candidate["equation_rows"]]
        features = [tuple(sorted(int(value) for value in feature)) for feature in candidate["multiplier_features"]]
        descriptors = [
            (int(item[0]), tuple(sorted(int(value) for value in item[1])))
            for item in candidate["column_descriptors"]
        ]
        expected_descriptors = [(row, feature) for row in rows for feature in features]
        if descriptors != expected_descriptors:
            raise ValueError("column descriptors are not the declared row-feature product")
        coefficients = parse_exact_coefficients(candidate)
        if len(coefficients) != len(descriptors):
            raise ValueError("exact coefficient count does not match descriptors")
        if any(value not in support for feature in features for value in feature):
            raise ValueError("multiplier feature uses a variable outside the support")

        totals: dict[tuple[int, ...], tuple[Fraction, Fraction]] = {}
        row_cache: dict[int, dict[tuple[int, ...], int]] = {}
        nonzero_coefficients = 0
        for (row, feature), (real, imaginary) in zip(descriptors, coefficients):
            if real == 0 and imaginary == 0:
                continue
            nonzero_coefficients += 1
            polynomial = row_cache.setdefault(row, equation_terms(row, support))
            for monomial, integer_coefficient in polynomial.items():
                key = tuple(sorted(monomial + feature))
                old_real, old_imaginary = totals.get(key, (Fraction(0), Fraction(0)))
                totals[key] = (
                    old_real + integer_coefficient * real,
                    old_imaginary + integer_coefficient * imaginary,
                )

        constant = totals.pop(tuple(), (Fraction(0), Fraction(0)))
        if constant != (Fraction(1), Fraction(0)):
            return False, f"constant coefficient is {constant}, expected (1,0)", {
                "descriptor_count": len(descriptors),
                "nonzero_coefficients": nonzero_coefficients,
                "residual_monomials": len(totals),
            }
        residual = {
            monomial: coefficient
            for monomial, coefficient in totals.items()
            if coefficient != (Fraction(0), Fraction(0))
        }
        if residual:
            first = next(iter(sorted(residual.items())))
            return False, f"nonzero residual monomial {first[0]} has coefficient {first[1]}", {
                "descriptor_count": len(descriptors),
                "nonzero_coefficients": nonzero_coefficients,
                "residual_monomials": len(residual),
            }
        return True, None, {
            "descriptor_count": len(descriptors),
            "nonzero_coefficients": nonzero_coefficients,
            "residual_monomials": 0,
        }
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}", {
            "descriptor_count": 0,
            "nonzero_coefficients": 0,
            "residual_monomials": 0,
        }


def _serialise_fraction(value: Fraction) -> tuple[int, int]:
    return value.numerator, value.denominator


def certificate_signature(
    candidate: dict[str, Any],
    canonical_support_value: tuple[int, ...],
    tied_transformations: list[tuple[tuple[int, ...], tuple[int, ...], bytes]],
) -> tuple[str, dict[str, Any]]:
    coefficients = parse_exact_coefficients(candidate)
    descriptors = [
        (int(item[0]), tuple(sorted(int(value) for value in item[1])))
        for item in candidate["column_descriptors"]
    ]
    best_payload: dict[str, Any] | None = None
    best_encoded: str | None = None
    for vertex, color, mapping in tied_transformations:
        terms = []
        for (row, feature), (real, imaginary) in zip(descriptors, coefficients):
            if real == 0 and imaginary == 0:
                continue
            transformed_row = transform_coloring(row, vertex, color)
            transformed_feature = tuple(sorted(mapping[value] for value in feature))
            terms.append(
                [
                    transformed_row,
                    list(transformed_feature),
                    list(_serialise_fraction(real)),
                    list(_serialise_fraction(imaginary)),
                ]
            )
        terms.sort()
        payload = {
            "support": list(canonical_support_value),
            "terms": terms,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        if best_encoded is None or encoded < best_encoded:
            best_encoded = encoded
            best_payload = {
                "vertex_permutation": list(vertex),
                "color_permutation": list(color),
                "nonzero_terms": len(terms),
            }
    assert best_encoded is not None and best_payload is not None
    return hashlib.sha256(best_encoded.encode("utf-8")).hexdigest(), best_payload


def candidate_key(source_path: str, candidate: dict[str, Any], index: int) -> str:
    identifier = str(candidate.get("candidate_id") or f"index-{index}")
    return f"{source_path}::{identifier}"


def shard_for(key: str, shard_count: int) -> int:
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % shard_count


def process_candidate(candidate: dict[str, Any], source_path: str, source_run_id: int | None, index: int) -> dict[str, Any]:
    key = candidate_key(source_path, candidate, index)
    claimed = bool(candidate.get("exact_verified", False))
    record: dict[str, Any] = {
        "candidate_key": key,
        "candidate_id": str(candidate.get("candidate_id") or f"index-{index}"),
        "source_path": source_path,
        "source_run_id": source_run_id,
        "production_exact_verified": claimed,
        "scope": str(candidate.get("scope", "unknown")),
        "support_size": int(candidate.get("support_size", len(candidate.get("support_variables", [])))),
        "max_multiplier_degree": int(candidate.get("max_multiplier_degree", -1)),
        "certificate_score": float(candidate.get("certificate_score", float("inf"))),
    }
    if not claimed:
        record.update(
            independent_exact_verified=False,
            verification_error="production candidate is not marked exact",
            status="not_exact_claim",
        )
        return record

    verified, error, verification_metrics = independent_exact_verification(candidate)
    record.update(verification_metrics)
    record["independent_exact_verified"] = verified
    record["verification_error"] = error
    if not verified:
        record["status"] = "rejected_exact_claim"
        return record

    canonical, ties = canonical_support(candidate["support_variables"])
    support_id = stable_hash({"n": N, "d": D, "support": canonical})
    signature, transform = certificate_signature(candidate, canonical, ties)
    record.update(
        status="verified_exact",
        canonical_support_id=support_id,
        canonical_support_variables=list(canonical),
        canonical_certificate_signature=signature,
        canonical_transform=transform,
        support_automorphism_ties=len(ties),
    )
    return record


def process_stage1_shard(
    repo: Path,
    spec: dict[str, Any],
    shard_id: int,
    shard_count: int,
    *,
    seconds: int,
    max_attempts: int,
) -> dict[str, Any]:
    started = time.time()
    deadline = started + max(30, seconds - 180)
    archives = list(spec.get("candidate_archives", []))
    if not archives:
        raise ValueError("stage1 spec has no candidate_archives")

    all_entries: list[tuple[str, int | None, int, dict[str, Any]]] = []
    archive_counts: dict[str, int] = {}
    archive_exact_counts: dict[str, int] = {}
    exact_only = bool(spec.get("exact_only", True))
    for source in archives:
        path = str(source["path"] if isinstance(source, dict) else source)
        run_id = int(source["run_id"]) if isinstance(source, dict) and source.get("run_id") is not None else None
        absolute = repo / path
        if not absolute.is_file():
            raise FileNotFoundError(f"missing candidate archive: {path}")
        document = read_gzip_json(absolute)
        candidates = list(document.get("candidates", []))
        archive_counts[path] = len(candidates)
        archive_exact_counts[path] = sum(1 for candidate in candidates if candidate.get("exact_verified") is True)
        for index, candidate in enumerate(candidates):
            if not isinstance(candidate, dict):
                continue
            if exact_only and candidate.get("exact_verified") is not True:
                continue
            key = candidate_key(path, candidate, index)
            if shard_for(key, shard_count) == shard_id:
                all_entries.append((path, run_id, index, candidate))

    assigned = len(all_entries)
    records: list[dict[str, Any]] = []
    deadline_hit = False
    limited = False
    for position, (path, run_id, index, candidate) in enumerate(all_entries):
        if max_attempts > 0 and len(records) >= max_attempts:
            limited = True
            break
        if time.time() >= deadline:
            deadline_hit = True
            break
        records.append(process_candidate(candidate, path, run_id, index))

    complete = not deadline_hit and not limited and len(records) == assigned
    metrics = {
        "archives": len(archives),
        "global_raw_candidates": sum(archive_counts.values()),
        "global_claimed_exact": sum(archive_exact_counts.values()),
        "assigned_candidates": assigned,
        "processed_candidates": len(records),
        "production_exact_claims": sum(1 for record in records if record["production_exact_verified"]),
        "independently_verified": sum(1 for record in records if record.get("independent_exact_verified") is True),
        "rejected_exact_claims": sum(1 for record in records if record.get("status") == "rejected_exact_claim"),
        "non_exact_candidates": sum(1 for record in records if record.get("status") == "not_exact_claim"),
        "canonical_support_classes_within_shard": len({record.get("canonical_support_id") for record in records if record.get("canonical_support_id")}),
        "canonical_certificate_signatures_within_shard": len({record.get("canonical_certificate_signature") for record in records if record.get("canonical_certificate_signature")}),
        "deadline_hit": deadline_hit,
        "limited_by_max_attempts": limited,
        "complete": complete,
    }
    return {
        "schema_version": 1,
        "task": "stage1_canonicalize_verify",
        "shard_id": shard_id,
        "shard_count": shard_count,
        "complete": complete,
        "archive_counts": archive_counts,
        "archive_exact_counts": archive_exact_counts,
        "metrics": metrics,
        "records": records,
        "unreadable": [],
    }
