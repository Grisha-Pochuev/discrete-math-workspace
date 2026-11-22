#!/usr/bin/env python3
"""Exact finite-event contract shared by the run-072 tools."""

from __future__ import annotations

from collections import Counter
import gzip
import hashlib
import itertools
import json
from pathlib import Path


VERTICES = tuple(range(8))
COLOURS = (0, 1, 2)
BINARY_SUPPORT = {
    (0, 1, 0, 0), (2, 3, 0, 0), (4, 5, 0, 0), (6, 7, 0, 0),
    (0, 7, 1, 1), (1, 2, 1, 1), (3, 4, 1, 1), (5, 6, 1, 1),
    (0, 6, 1, 0), (1, 3, 1, 0), (2, 4, 1, 1), (5, 7, 1, 1),
    (3, 4, 0, 1), (5, 6, 1, 0),
}
THIRD_TARGET = {(0, 4), (1, 5), (2, 3), (6, 7)}


def canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def perfect_matchings(vertices):
    vertices = tuple(vertices)
    if not vertices:
        yield ()
        return
    first = vertices[0]
    for position, second in enumerate(vertices[1:], start=1):
        rest = vertices[1:position] + vertices[position + 1:]
        for tail in perfect_matchings(rest):
            yield ((first, second),) + tail


MATCHINGS = tuple(perfect_matchings(VERTICES))
assert len(MATCHINGS) == 105


def edge_entry(edge, colouring):
    left, right = edge
    return left, right, colouring[left], colouring[right]


def encode_entry(value):
    return {
        "edge": [value[0], value[1]],
        "endpoint_colours": [value[2], value[3]],
    }


def fixed_support():
    return BINARY_SUPPORT | {(left, right, 2, 2) for left, right in THIRD_TARGET}


def candidate_entries():
    fixed = fixed_support()
    result = tuple(sorted(
        (left, right, left_colour, right_colour)
        for left, right in itertools.combinations(VERTICES, 2)
        for left_colour, right_colour in itertools.product(COLOURS, repeat=2)
        if (left, right, left_colour, right_colour) not in fixed
    ))
    if len(result) != 234:
        raise AssertionError("candidate coverage mismatch")
    return result


def candidate_catalogue():
    return [encode_entry(value) for value in candidate_entries()]


def build_rows(candidates):
    fixed = fixed_support()
    candidate_index = {value: index for index, value in enumerate(candidates)}
    forbidden = []
    targets = []
    for colouring in itertools.product(COLOURS, repeat=8):
        masks = []
        for matching in MATCHINGS:
            mask = 0
            possible = True
            for edge in matching:
                value = edge_entry(edge, colouring)
                if value in fixed:
                    continue
                index = candidate_index.get(value)
                if index is None:
                    possible = False
                    break
                mask |= 1 << index
            if possible:
                masks.append(mask)
        row = (colouring, tuple(sorted(Counter(masks).items())))
        if len(set(colouring)) == 1:
            targets.append(row)
        elif masks:
            forbidden.append(row)
    if len(targets) != 3 or len(forbidden) > 3 ** 8 - 3:
        raise AssertionError("row coverage mismatch")
    return tuple(forbidden), tuple(targets)


def clause_key(required, alternatives):
    return tuple(required), tuple(tuple(item) for item in alternatives)


def validate_clause(clause, candidate_count=234):
    required = clause["required"]
    alternatives = clause["alternatives"]
    if required != sorted(set(required)) or not alternatives:
        raise ValueError("invalid clause support")
    if any(not 0 <= item < candidate_count for item in required):
        raise ValueError("clause variable out of range")
    seen = set()
    for monomial in alternatives:
        if monomial != sorted(set(monomial)):
            raise ValueError("invalid alternative monomial")
        if any(not 0 <= item < candidate_count for item in monomial):
            raise ValueError("alternative variable out of range")
        current = tuple(monomial)
        if current in seen:
            raise ValueError("duplicate alternative monomial")
        seen.add(current)


def load_compact_input(path, expected_sha256, expected_outcome):
    path = Path(path)
    if sha256_file(path) != expected_sha256:
        raise ValueError("compact input identity mismatch")
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        payload = json.load(stream)
    copy = dict(payload)
    claimed = copy.pop("canonical_outcome_sha256")
    if (
        payload.get("schema") != "finite-event-search-input-v1"
        or hashlib.sha256(canonical_bytes(copy)).hexdigest() != claimed
        or claimed != expected_outcome
        or payload.get("candidate_catalogue") != candidate_catalogue()
        or payload.get("source_event_record_count") != 377
        or payload.get("source_clause_count") != len(payload.get("source_clauses", []))
        or payload.get("learned_clause_count") != len(payload.get("learned_clauses", []))
        or payload.get("total_clause_count") != (
            payload.get("source_clause_count") + payload.get("learned_clause_count")
        )
    ):
        raise ValueError("compact input contract mismatch")
    keys = set()
    for clause in payload["source_clauses"] + payload["learned_clauses"]:
        validate_clause(clause)
        key = clause_key(clause["required"], clause["alternatives"])
        if key in keys:
            raise ValueError("duplicate compact clause")
        keys.add(key)
    if len(keys) != 1887:
        raise ValueError("compact clause coverage mismatch")
    return payload


def mask_indices(mask, candidate_count=234):
    return [index for index in range(candidate_count) if mask >> index & 1]


def scan_support(support, rows, candidate_count, limit):
    complement = ~support
    threats = []
    total_threats = 0
    histogram = Counter()
    for row_index, (colouring, masks) in enumerate(rows):
        supported = [
            (mask, multiplicity) for mask, multiplicity in masks
            if mask & complement == 0
        ]
        count = sum(multiplicity for _mask, multiplicity in supported)
        target = len(set(colouring)) == 1
        violated = count == (2 if target else 1)
        histogram[("target_" if target else "forbidden_") + (
            "0" if count == 0 else "1" if count == 1 else "2+"
        )] += 1
        if not violated:
            continue
        total_threats += 1
        if len(threats) >= limit:
            continue
        supported_masks = sorted(mask for mask, _multiplicity in supported)
        alternatives = sorted(mask for mask, _multiplicity in masks if mask & complement)
        required = sorted({
            index for mask in supported_masks for index in mask_indices(mask, candidate_count)
        })
        threats.append({
            "row_index": row_index,
            "colouring": list(colouring),
            "target": target,
            "supported_count": count,
            "supported_monomials": [mask_indices(mask, candidate_count) for mask in supported_masks],
            "required": required,
            "alternatives": [mask_indices(mask, candidate_count) for mask in alternatives],
        })
    return threats, total_threats, dict(sorted(histogram.items()))


def constraints_hold(support, rows):
    complement = ~support
    for colouring, masks in rows:
        count = sum(
            multiplicity for mask, multiplicity in masks if mask & complement == 0
        )
        if count == (2 if len(set(colouring)) == 1 else 1):
            return False
    return True


def validate_dynamic_clause(record, rows, candidate_count=234):
    validate_clause(record, candidate_count)
    row_index = record["row_index"]
    if not 0 <= row_index < len(rows):
        raise ValueError("dynamic row index out of range")
    colouring, masks = rows[row_index]
    if list(colouring) != record["colouring"]:
        raise ValueError("dynamic colouring mismatch")
    target = len(set(colouring)) == 1
    if target != record["target"]:
        raise ValueError("dynamic target flag mismatch")
    multiplicity = dict(masks)
    alternative_masks = [
        sum(1 << item for item in monomial)
        for monomial in record["alternatives"]
    ]
    supported_masks = sorted(set(multiplicity) - set(alternative_masks))
    if (
        alternative_masks != sorted(set(alternative_masks))
        or set(supported_masks) & set(alternative_masks)
        or set(supported_masks) | set(alternative_masks) != set(multiplicity)
        or sum(multiplicity[item] for item in supported_masks) != record["supported_count"]
        or record["supported_count"] != (2 if target else 1)
        or record["required"] != sorted({
            item for mask in supported_masks for item in mask_indices(mask, candidate_count)
        })
    ):
        raise ValueError("dynamic row partition mismatch")


def exact_survivor_payload(support, candidates, forbidden_rows, target_rows):
    all_rows = forbidden_rows + target_rows
    if not constraints_hold(support, all_rows):
        raise ValueError("survivor violates an exact row")
    histogram = Counter()
    complement = ~support
    for colouring, masks in all_rows:
        count = sum(
            multiplicity for mask, multiplicity in masks if mask & complement == 0
        )
        histogram[("target_" if len(set(colouring)) == 1 else "forbidden_") + (
            "0" if count == 0 else "1" if count == 1 else "2+"
        )] += 1
    selected = mask_indices(support, len(candidates))
    payload = {
        "schema": "run-072-finite-events-survivor-v1",
        "evidence_level": "independent exact replay of every finite row",
        "selected_indices": selected,
        "selected_entries": [encode_entry(candidates[index]) for index in selected],
        "selected_count": len(selected),
        "row_histogram": dict(sorted(histogram.items())),
        "forbidden_rows_replayed": len(forbidden_rows),
        "target_rows_replayed": len(target_rows),
        "accepted": True,
        "scope_warning": "This is a finite support survivor; it still requires exact coefficient analysis.",
    }
    payload["canonical_outcome_sha256"] = hashlib.sha256(canonical_bytes(payload)).hexdigest()
    return payload
