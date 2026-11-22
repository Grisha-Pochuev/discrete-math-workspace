#!/usr/bin/env python3
"""Bridge compact exact certificates to Second approach numerical candidates.

The analysis is deliberately exact on the obstruction side.  A candidate is
called covered only when a transformed three-term rational certificate is
re-verified on that candidate support.  A small Hamming distance, a low
floating-point residual, or an unfinished neighborhood scan is never called a
proof.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import gzip
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import random
import time
from typing import Any, Iterable

N = 6
D = 3
EDGES = tuple((i, j) for i in range(N) for j in range(i + 1, N))
EDGE_INDEX = {edge: index for index, edge in enumerate(EDGES)}
VARIABLE_COUNT = len(EDGES) * D * D
MONO_ROWS = (0, 364, 728)
INDEPENDENT_LANES = {
    "fresh_independent", "obstruction_boundary", "novelty_far",
    "independent_precision", "independent_mutation",
}


def read_gzip_json(path: Path) -> Any:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def write_gzip_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with gzip.open(temporary, "wt", encoding="utf-8", compresslevel=9) as handle:
        json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
    os.replace(temporary, path)


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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
    value = int(row)
    for position in range(N - 1, -1, -1):
        value, values[position] = divmod(value, D)
    return tuple(values)


def encode_coloring(colors: Iterable[int]) -> int:
    result = 0
    for value in colors:
        result = result * D + int(value)
    return result


def _perfect_matchings(vertices: tuple[int, ...]) -> tuple[tuple[tuple[int, int], ...], ...]:
    if not vertices:
        return (tuple(),)
    first = vertices[0]
    result = []
    for position in range(1, len(vertices)):
        second = vertices[position]
        remaining = vertices[1:position] + vertices[position + 1:]
        edge = (min(first, second), max(first, second))
        for tail in _perfect_matchings(remaining):
            result.append((edge,) + tail)
    return tuple(result)


MATCHINGS = _perfect_matchings(tuple(range(N)))
_TRANSFORMATIONS: list[tuple[tuple[int, ...], tuple[int, ...], bytes]] | None = None


def transformations() -> list[tuple[tuple[int, ...], tuple[int, ...], bytes]]:
    global _TRANSFORMATIONS
    if _TRANSFORMATIONS is not None:
        return _TRANSFORMATIONS
    result = []
    for vertex in itertools.permutations(range(N)):
        for color in itertools.permutations(range(D)):
            mapping = bytearray(VARIABLE_COUNT)
            for value in range(VARIABLE_COUNT):
                i, j, a, b = decode_variable(value)
                mapping[value] = variable_index(vertex[i], vertex[j], color[a], color[b])
            result.append((vertex, color, bytes(mapping)))
    _TRANSFORMATIONS = result
    return result


def transform_coloring(row: int, vertex: tuple[int, ...], color: tuple[int, ...]) -> int:
    old = decode_coloring(row)
    new = [0] * N
    for old_vertex, old_color in enumerate(old):
        new[vertex[old_vertex]] = color[old_color]
    return encode_coloring(new)


def transform_support(support: Iterable[int], mapping: bytes) -> tuple[int, ...]:
    return tuple(sorted(mapping[int(value)] for value in support))


def mask_from_values(values: Iterable[int]) -> int:
    result = 0
    for value in values:
        result |= 1 << int(value)
    return result


def values_from_mask(mask: int) -> tuple[int, ...]:
    values = []
    bit = 0
    mask = int(mask)
    while mask:
        if mask & 1:
            values.append(bit)
        bit += 1
        mask >>= 1
    return tuple(values)


def candidate_mask(candidate: dict[str, Any]) -> int:
    raw = candidate.get("support_mask_hex")
    if raw not in (None, ""):
        return int(str(raw), 16)
    values = candidate.get("active_variables")
    if isinstance(values, list):
        return mask_from_values(int(value) for value in values)
    raise ValueError("candidate has neither support_mask_hex nor active_variables")


def canonical_support(support: Iterable[int]) -> tuple[tuple[int, ...], list[tuple[tuple[int, ...], tuple[int, ...], bytes]]]:
    values = tuple(sorted(set(int(value) for value in support)))
    best = None
    ties = []
    for vertex, color, mapping in transformations():
        transformed = transform_support(values, mapping)
        if best is None or transformed < best:
            best = transformed
            ties = [(vertex, color, mapping)]
        elif transformed == best:
            ties.append((vertex, color, mapping))
    if best is None:
        raise ValueError("empty transformation set")
    return best, ties


def _fraction(raw: Any) -> Fraction:
    return Fraction(int(raw[0]), int(raw[1]))


def deserialize_terms(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "row": int(item["row"]),
            "feature": tuple(sorted(int(value) for value in item.get("feature", []))),
            "real": _fraction(item["real"]),
            "imag": _fraction(item["imag"]),
        }
        for item in items
    ]


def serialize_terms(terms: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for term in terms:
        real = Fraction(term["real"])
        imag = Fraction(term["imag"])
        result.append({
            "row": int(term["row"]),
            "feature": [int(value) for value in term["feature"]],
            "real": [real.numerator, real.denominator],
            "imag": [imag.numerator, imag.denominator],
        })
    return sorted(result, key=lambda item: (item["row"], item["feature"], item["real"], item["imag"]))


def transform_terms(
    terms: Iterable[dict[str, Any]],
    vertex: tuple[int, ...],
    color: tuple[int, ...],
    mapping: bytes,
) -> list[dict[str, Any]]:
    return [
        {
            "row": transform_coloring(int(term["row"]), vertex, color),
            "feature": tuple(sorted(mapping[int(value)] for value in term["feature"])),
            "real": Fraction(term["real"]),
            "imag": Fraction(term["imag"]),
        }
        for term in terms
    ]


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


def verify_sparse_certificate(support_values: Iterable[int], terms: Iterable[dict[str, Any]]) -> tuple[bool, str | None]:
    support = tuple(sorted(set(int(value) for value in support_values)))
    support_set = set(support)
    totals: dict[tuple[int, ...], tuple[Fraction, Fraction]] = {}
    for term in terms:
        feature = tuple(int(value) for value in term["feature"])
        if any(value not in support_set for value in feature):
            return False, "feature outside candidate support"
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


def mono_matching_counts(support_values: Iterable[int]) -> tuple[int, int, int]:
    support = tuple(sorted(set(int(value) for value in support_values)))
    return tuple(sum(1 for monomial in equation_terms(row, support) if monomial) for row in MONO_ROWS)  # type: ignore[return-value]


def prepare_mechanisms(run004_path: Path, run001_classes_path: Path, shard_id: int = 0, shard_count: int = 1) -> dict[str, Any]:
    run004 = read_gzip_json(run004_path)
    records = list(run004.get("records", []))
    classes_doc = json.loads(run001_classes_path.read_text(encoding="utf-8"))
    class_supports = {
        str(item["canonical_support_id"]): tuple(int(value) for value in item["canonical_support_variables"])
        for item in classes_doc.get("classes", [])
    }
    mechanisms = []
    errors = []
    for index, record in enumerate(records):
        if index % shard_count != shard_id:
            continue
        support_id = str(record["canonical_support_id"])
        canonical = class_supports.get(support_id)
        if canonical is None:
            errors.append({"index": index, "error": "missing canonical support", "support_id": support_id})
            continue
        original_support = tuple(int(value) for value in record["fixed_support_variables"])
        terms = deserialize_terms(record["minimized_terms"])
        variants: dict[str, list[dict[str, Any]]] = {}
        for vertex, color, mapping in transformations():
            if transform_support(original_support, mapping) != canonical:
                continue
            transformed = transform_terms(terms, vertex, color, mapping)
            valid, error = verify_sparse_certificate(canonical, transformed)
            if not valid:
                errors.append({"index": index, "error": error, "support_id": support_id})
                continue
            serialized = serialize_terms(transformed)
            encoded = json.dumps(serialized, sort_keys=True, separators=(",", ":"))
            variants.setdefault(hashlib.sha256(encoded.encode()).hexdigest(), serialized)
        if not variants:
            errors.append({"index": index, "error": "no exact canonical certificate variant", "support_id": support_id})
            continue
        variant_list = [variants[key] for key in sorted(variants)]
        best = variant_list[0]
        mechanism_id = stable_hash({"support": canonical, "terms": best})
        mechanisms.append({
            "mechanism_id": mechanism_id,
            "canonical_support_id": support_id,
            "canonical_support_variables": list(canonical),
            "canonical_support_mask_hex": hex(mask_from_values(canonical)),
            "support_size": len(canonical),
            "certificate_variants": variant_list,
            "variant_count": len(variant_list),
            "member_candidate_id": record.get("candidate_id"),
            "member_source_path": record.get("source_path"),
        })
    if errors:
        raise ValueError(f"mechanism preparation errors: {errors[:3]}")
    by_mechanism: dict[str, dict[str, Any]] = {}
    for mechanism in mechanisms:
        key = str(mechanism["mechanism_id"])
        entry = by_mechanism.setdefault(key, dict(mechanism, member_count=0, support_ids=[]))
        entry["member_count"] += 1
        entry["support_ids"].append(str(mechanism["canonical_support_id"]))
    unique = [by_mechanism[key] for key in sorted(by_mechanism)]
    support_map = {str(item["canonical_support_id"]): item for item in mechanisms}
    return {
        "schema_version": 1,
        "task": "stage5_prepare_exact_mechanisms",
        "source_run004_records": len(records),
        "shard_id": shard_id,
        "shard_count": shard_count,
        "processed_run004_records": len(mechanisms),
        "canonical_mechanism_classes": len(unique),
        "support_classes": len(support_map),
        "mechanism_classes": unique,
        "support_mechanisms": [support_map[key] for key in sorted(support_map)],
    }


def merge_mechanism_parts(parts_root: Path) -> dict[str, Any]:
    paths = sorted(parts_root.rglob("mechanisms-part-*.json.gz"))
    if not paths:
        raise ValueError("no mechanism part files")
    source_totals: set[int] = set()
    shard_counts: set[int] = set()
    shard_ids: set[int] = set()
    mechanisms: list[dict[str, Any]] = []
    for path in paths:
        part = read_gzip_json(path)
        source_totals.add(int(part.get("source_run004_records", -1)))
        shard_counts.add(int(part.get("shard_count", -1)))
        shard_ids.add(int(part.get("shard_id", -1)))
        mechanisms.extend(list(part.get("support_mechanisms", [])))
    if len(source_totals) != 1 or len(shard_counts) != 1:
        raise ValueError("inconsistent mechanism part metadata")
    source_total = next(iter(source_totals))
    shard_count = next(iter(shard_counts))
    if shard_ids != set(range(shard_count)):
        raise ValueError(f"missing mechanism shards: {sorted(set(range(shard_count)) - shard_ids)}")
    support_map: dict[str, dict[str, Any]] = {}
    for item in mechanisms:
        key = str(item["canonical_support_id"])
        if key in support_map and support_map[key] != item:
            raise ValueError(f"conflicting mechanism support {key}")
        support_map[key] = item
    if len(support_map) != source_total:
        raise ValueError(f"mechanism coverage {len(support_map)} != source {source_total}")
    by_mechanism: dict[str, dict[str, Any]] = {}
    for item in support_map.values():
        key = str(item["mechanism_id"])
        entry = by_mechanism.setdefault(key, dict(item, member_count=0, support_ids=[]))
        entry["member_count"] += 1
        entry["support_ids"].append(str(item["canonical_support_id"]))
    return {
        "schema_version": 1,
        "task": "stage5_prepare_exact_mechanisms",
        "source_run004_records": source_total,
        "canonical_mechanism_classes": len(by_mechanism),
        "support_classes": len(support_map),
        "mechanism_classes": [by_mechanism[key] for key in sorted(by_mechanism)],
        "support_mechanisms": [support_map[key] for key in sorted(support_map)],
    }


def candidate_group(candidate: dict[str, Any], source_kind: str) -> str:
    if source_kind == "old_seed_bank":
        return "old_pool"
    if bool(candidate.get("legacy_rooted", False)):
        return "legacy_2_0"
    if str(candidate.get("lineage_origin", "")) == "independent":
        return "independent_2_0"
    if str(candidate.get("lane", "")) in INDEPENDENT_LANES:
        return "independent_2_0"
    root = str(candidate.get("lineage_root") or candidate.get("candidate_id") or "")
    if root.startswith("sa20-"):
        return "independent_2_0"
    return "legacy_2_0"


def load_candidates(old_bank: Path, second20_bank: Path) -> list[dict[str, Any]]:
    result = []
    for source_kind, path in (("old_seed_bank", old_bank), ("second_approach_2_0", second20_bank)):
        document = read_gzip_json(path)
        for index, raw in enumerate(document.get("candidates", [])):
            if not isinstance(raw, dict):
                continue
            candidate = dict(raw)
            identifier = str(candidate.get("candidate_id") or f"index-{index}")
            try:
                mask = candidate_mask(candidate)
            except Exception:
                continue
            score = float(candidate.get("max_error", 1e300))
            if not math.isfinite(score):
                score = 1e300
            result.append({
                "candidate_key": f"{source_kind}::{identifier}",
                "source_kind": source_kind,
                "group": candidate_group(candidate, source_kind),
                "candidate_id": identifier,
                "max_error": score,
                "lane": candidate.get("lane"),
                "lineage_root": candidate.get("lineage_root"),
                "lineage_depth": candidate.get("lineage_depth"),
                "support_mask_hex": hex(mask),
                "support_size": mask.bit_count(),
                "support_fingerprint": candidate.get("support_fingerprint"),
                "residual_basin_fingerprint": candidate.get("residual_basin_fingerprint"),
                "legacy_rooted": bool(candidate.get("legacy_rooted", source_kind == "old_seed_bank")),
            })
    return sorted(result, key=lambda item: (item["group"], item["max_error"], item["candidate_key"]))


def lane_for_candidate(key: str, lanes: int) -> int:
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % lanes


def nearest_canonical(candidate_mask_value: int, mechanisms: list[dict[str, Any]], limit: int = 32) -> list[dict[str, Any]]:
    ranked = []
    for mechanism in mechanisms:
        mechanism_mask = int(str(mechanism["canonical_support_mask_hex"]), 16)
        removed = (mechanism_mask & ~candidate_mask_value).bit_count()
        added = (candidate_mask_value & ~mechanism_mask).bit_count()
        ranked.append((removed + added, removed, added, str(mechanism["canonical_support_id"]), mechanism))
    ranked.sort(key=lambda item: item[:4])
    return [dict(item[4], distance=item[0], mechanism_only=item[1], candidate_only=item[2]) for item in ranked[:limit]]


def test_mechanism_on_support(support: tuple[int, ...], mechanism: dict[str, Any]) -> tuple[bool, int | None]:
    for index, raw_terms in enumerate(mechanism.get("certificate_variants", [])):
        terms = deserialize_terms(raw_terms)
        valid, _ = verify_sparse_certificate(support, terms)
        if valid:
            return True, index
    return False, None


def transform_mask(mask: int, mapping: bytes) -> int:
    result = 0
    value = int(mask)
    bit = 0
    while value:
        if value & 1:
            result |= 1 << mapping[bit]
        value >>= 1
        bit += 1
    return result


def orbit_nearest(mask: int, mechanisms: list[dict[str, Any]], limit: int = 16) -> list[dict[str, Any]]:
    exact_masks = [(int(str(item["canonical_support_mask_hex"]), 16), item) for item in mechanisms]
    best: dict[str, tuple[int, int, int, int, dict[str, Any]]] = {}
    for transform_index, (_vertex, _color, mapping) in enumerate(transformations()):
        transformed = transform_mask(mask, mapping)
        for exact_mask, mechanism in exact_masks:
            distance = (transformed ^ exact_mask).bit_count()
            key = str(mechanism["canonical_support_id"])
            previous = best.get(key)
            if previous is None or distance < previous[0]:
                best[key] = (
                    distance,
                    (exact_mask & ~transformed).bit_count(),
                    (transformed & ~exact_mask).bit_count(),
                    transform_index,
                    mechanism,
                )
    ranked = sorted(best.values(), key=lambda item: (item[0], item[1], item[2], str(item[4]["canonical_support_id"])))[:limit]
    return [
        dict(item[4], distance=item[0], mechanism_only=item[1], candidate_only=item[2], transform_index=item[3])
        for item in ranked
    ]


def canonical_record(candidate: dict[str, Any], mechanisms: list[dict[str, Any]], support_lookup: dict[str, dict[str, Any]]) -> dict[str, Any]:
    mask = int(candidate["support_mask_hex"], 16)
    support = values_from_mask(mask)
    canonical, ties = canonical_support(support)
    canonical_mask = mask_from_values(canonical)
    support_id = stable_hash({"n": N, "d": D, "support": canonical})
    coverage = None
    mechanism = support_lookup.get(support_id)
    if mechanism is not None:
        valid, variant = test_mechanism_on_support(canonical, mechanism)
        if not valid:
            raise ValueError(f"exact support match failed certificate verification: {candidate['candidate_key']}")
        coverage = {
            "kind": "exact_support_class",
            "canonical_support_id": support_id,
            "mechanism_id": mechanism["mechanism_id"],
            "variant_index": variant,
            "distance": 0,
        }
    nearest = nearest_canonical(canonical_mask, mechanisms, 32)
    if coverage is None:
        for item in nearest:
            valid, variant = test_mechanism_on_support(canonical, item)
            if valid:
                coverage = {
                    "kind": "canonical_alignment_certificate",
                    "canonical_support_id": item["canonical_support_id"],
                    "mechanism_id": item["mechanism_id"],
                    "variant_index": variant,
                    "distance": item["distance"],
                }
                break
    return {
        **candidate,
        "canonical_support_id": support_id,
        "canonical_support_mask_hex": hex(canonical_mask),
        "canonical_support_size": len(canonical),
        "canonical_automorphism_ties": len(ties),
        "mono_matching_counts": list(mono_matching_counts(support)),
        "baseline_coverage": coverage,
        "nearest_canonical": [
            {
                "canonical_support_id": item["canonical_support_id"],
                "mechanism_id": item["mechanism_id"],
                "distance": item["distance"],
                "mechanism_only": item["mechanism_only"],
                "candidate_only": item["candidate_only"],
            }
            for item in nearest[:8]
        ],
        "orbit_scan_complete": False,
        "orbit_coverage": None,
        "orbit_nearest": [],
        "radius1_complete": False,
        "radius1_exact_hits": [],
        "radius2_samples": 0,
        "radius2_exact_hits": [],
    }


def refine_orbit(record: dict[str, Any], mechanisms: list[dict[str, Any]]) -> None:
    mask = int(record["support_mask_hex"], 16)
    nearest = orbit_nearest(mask, mechanisms, 16)
    coverage = None
    transforms = transformations()
    for item in nearest:
        _vertex, _color, mapping = transforms[int(item["transform_index"])]
        transformed_support = values_from_mask(transform_mask(mask, mapping))
        valid, variant = test_mechanism_on_support(transformed_support, item)
        if valid:
            coverage = {
                "kind": "orbit_aligned_certificate",
                "canonical_support_id": item["canonical_support_id"],
                "mechanism_id": item["mechanism_id"],
                "variant_index": variant,
                "distance": item["distance"],
                "transform_index": item["transform_index"],
            }
            break
    record["orbit_scan_complete"] = True
    record["orbit_coverage"] = coverage
    record["orbit_nearest"] = [
        {
            "canonical_support_id": item["canonical_support_id"],
            "mechanism_id": item["mechanism_id"],
            "distance": item["distance"],
            "mechanism_only": item["mechanism_only"],
            "candidate_only": item["candidate_only"],
            "transform_index": item["transform_index"],
        }
        for item in nearest[:8]
    ]


def radius1_frontier(record: dict[str, Any], support_lookup: dict[str, dict[str, Any]], deadline: float) -> None:
    mask = int(record["support_mask_hex"], 16)
    hits = []
    for variable in range(VARIABLE_COUNT):
        if time.time() >= deadline:
            record["radius1_complete"] = False
            record["radius1_exact_hits"] = hits[:64]
            return
        neighbor = mask ^ (1 << variable)
        support = values_from_mask(neighbor)
        if not all(value > 0 for value in mono_matching_counts(support)):
            continue
        canonical, _ties = canonical_support(support)
        support_id = stable_hash({"n": N, "d": D, "support": canonical})
        mechanism = support_lookup.get(support_id)
        if mechanism is not None:
            hits.append({
                "edited_variable": variable,
                "edit": "remove" if mask & (1 << variable) else "add",
                "canonical_support_id": support_id,
                "mechanism_id": mechanism["mechanism_id"],
            })
    record["radius1_complete"] = True
    record["radius1_exact_hits"] = hits[:64]


def radius2_sample(record: dict[str, Any], support_lookup: dict[str, dict[str, Any]], rng: random.Random, samples: int, deadline: float) -> None:
    mask = int(record["support_mask_hex"], 16)
    seen = set()
    hits = list(record.get("radius2_exact_hits", []))
    for _ in range(samples):
        if time.time() >= deadline:
            break
        a = rng.randrange(VARIABLE_COUNT)
        b = rng.randrange(VARIABLE_COUNT - 1)
        if b >= a:
            b += 1
        pair = (min(a, b), max(a, b))
        if pair in seen:
            continue
        seen.add(pair)
        neighbor = mask ^ (1 << a) ^ (1 << b)
        support = values_from_mask(neighbor)
        if not all(value > 0 for value in mono_matching_counts(support)):
            continue
        canonical, _ties = canonical_support(support)
        support_id = stable_hash({"n": N, "d": D, "support": canonical})
        mechanism = support_lookup.get(support_id)
        if mechanism is not None:
            hits.append({
                "edited_variables": [a, b],
                "canonical_support_id": support_id,
                "mechanism_id": mechanism["mechanism_id"],
            })
    record["radius2_samples"] = int(record.get("radius2_samples", 0)) + len(seen)
    record["radius2_exact_hits"] = hits[:64]


def checkpoint_payload(records: dict[str, dict[str, Any]], assigned: int, global_count: int, lane_id: int, lane_count: int, *, baseline_complete: bool, started: float) -> dict[str, Any]:
    values = [records[key] for key in sorted(records)]
    return {
        "schema_version": 1,
        "task": "stage5_bridge_second_approach",
        "lane_id": lane_id,
        "lane_count": lane_count,
        "global_candidate_count": global_count,
        "assigned_candidates": assigned,
        "baseline_complete": baseline_complete,
        "records": values,
        "metrics": {
            "assigned_candidates": assigned,
            "baseline_records": len(values),
            "baseline_exact_coverage": sum(record.get("baseline_coverage") is not None for record in values),
            "orbit_scans_complete": sum(bool(record.get("orbit_scan_complete")) for record in values),
            "orbit_exact_coverage": sum(record.get("orbit_coverage") is not None for record in values),
            "radius1_complete": sum(bool(record.get("radius1_complete")) for record in values),
            "radius1_exact_hits": sum(len(record.get("radius1_exact_hits", [])) for record in values),
            "radius2_samples": sum(int(record.get("radius2_samples", 0)) for record in values),
            "radius2_exact_hits": sum(len(record.get("radius2_exact_hits", [])) for record in values),
            "elapsed_seconds": time.time() - started,
        },
    }


def analyze_lane(
    mechanisms_path: Path,
    old_bank: Path,
    second20_bank: Path,
    job_id: int,
    worker_id: int,
    jobs: int,
    workers_per_job: int,
    seconds: int,
    output: Path,
) -> dict[str, Any]:
    library = read_gzip_json(mechanisms_path)
    mechanisms = list(library.get("support_mechanisms", []))
    support_lookup = {str(item["canonical_support_id"]): item for item in mechanisms}
    candidates = load_candidates(old_bank, second20_bank)
    lane_count = jobs * workers_per_job
    lane_id = job_id * workers_per_job + worker_id
    assigned = [item for item in candidates if lane_for_candidate(item["candidate_key"], lane_count) == lane_id]
    started = time.time()
    deadline = started + max(60, seconds - 300)
    records: dict[str, dict[str, Any]] = {}
    for candidate in assigned:
        records[candidate["candidate_key"]] = canonical_record(candidate, mechanisms, support_lookup)
        if len(records) % 4 == 0:
            write_gzip_json(output, checkpoint_payload(records, len(assigned), len(candidates), lane_id, lane_count, baseline_complete=False, started=started))
    write_gzip_json(output, checkpoint_payload(records, len(assigned), len(candidates), lane_id, lane_count, baseline_complete=True, started=started))

    priority = sorted(
        records.values(),
        key=lambda item: (
            item.get("baseline_coverage") is not None,
            0 if item["group"] == "old_pool" else 1 if item["group"] == "legacy_2_0" else 2,
            float(item.get("max_error", math.inf)),
            item["candidate_key"],
        ),
    )
    for record in priority:
        if time.time() >= deadline:
            break
        if record.get("baseline_coverage") is None:
            refine_orbit(record, mechanisms)
        else:
            record["orbit_scan_complete"] = True
            record["orbit_coverage"] = record["baseline_coverage"]
        write_gzip_json(output, checkpoint_payload(records, len(assigned), len(candidates), lane_id, lane_count, baseline_complete=True, started=started))

    for record in priority:
        if time.time() >= deadline:
            break
        if record.get("baseline_coverage") is None and record.get("orbit_coverage") is None:
            radius1_frontier(record, support_lookup, deadline)
            write_gzip_json(output, checkpoint_payload(records, len(assigned), len(candidates), lane_id, lane_count, baseline_complete=True, started=started))

    rng = random.Random(5_000_011 + lane_id)
    hard = [
        record for record in priority
        if record.get("baseline_coverage") is None and record.get("orbit_coverage") is None
    ]
    cursor = 0
    while hard and time.time() < deadline:
        record = hard[cursor % len(hard)]
        radius2_sample(record, support_lookup, rng, 8, deadline)
        cursor += 1
        if cursor % 4 == 0:
            write_gzip_json(output, checkpoint_payload(records, len(assigned), len(candidates), lane_id, lane_count, baseline_complete=True, started=started))
    payload = checkpoint_payload(records, len(assigned), len(candidates), lane_id, lane_count, baseline_complete=True, started=started)
    write_gzip_json(output, payload)
    return payload


def self_test() -> None:
    support = (variable_index(0, 1, 0, 0), variable_index(2, 3, 0, 0))
    terms = [{"row": 0, "feature": tuple(), "real": Fraction(-1), "imag": Fraction(0)}]
    valid, error = verify_sparse_certificate(support, terms)
    assert valid, error
    canonical, ties = canonical_support(support)
    assert len(canonical) == 2 and ties
    transformed = transform_terms(terms, *ties[0])
    assert verify_sparse_certificate(canonical, transformed)[0]
    assert mono_matching_counts(support)[0] == 0
    candidate = {"candidate_id": "synthetic", "support_mask_hex": hex(mask_from_values(support)), "max_error": 1.0}
    assert candidate_mask(candidate) == mask_from_values(support)
    print(json.dumps({"self_test": "ok", "transformations": len(transformations()), "canonical": canonical}))


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--run004", type=Path, required=True)
    prepare.add_argument("--run001-classes", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--shard-id", type=int, default=0)
    prepare.add_argument("--shard-count", type=int, default=1)
    merge_parser = sub.add_parser("merge-mechanisms")
    merge_parser.add_argument("--parts", type=Path, required=True)
    merge_parser.add_argument("--output", type=Path, required=True)
    analyze = sub.add_parser("analyze")
    analyze.add_argument("--mechanisms", type=Path, required=True)
    analyze.add_argument("--old-bank", type=Path, required=True)
    analyze.add_argument("--second20-bank", type=Path, required=True)
    analyze.add_argument("--job-id", type=int, required=True)
    analyze.add_argument("--worker-id", type=int, required=True)
    analyze.add_argument("--jobs", type=int, default=20)
    analyze.add_argument("--workers-per-job", type=int, default=4)
    analyze.add_argument("--seconds", type=int, default=20700)
    analyze.add_argument("--output", type=Path, required=True)
    sub.add_parser("self-test")
    args = parser.parse_args()
    if args.command == "self-test":
        self_test()
        return 0
    if args.command == "prepare":
        payload = prepare_mechanisms(args.run004, args.run001_classes, args.shard_id, args.shard_count)
        write_gzip_json(args.output, payload)
        print(json.dumps({key: payload[key] for key in ("source_run004_records", "canonical_mechanism_classes", "support_classes")}, indent=2))
        return 0
    if args.command == "merge-mechanisms":
        payload = merge_mechanism_parts(args.parts)
        write_gzip_json(args.output, payload)
        print(json.dumps({key: payload[key] for key in ("source_run004_records", "canonical_mechanism_classes", "support_classes")}, indent=2))
        return 0
    payload = analyze_lane(
        args.mechanisms, args.old_bank, args.second20_bank,
        args.job_id, args.worker_id, args.jobs, args.workers_per_job,
        args.seconds, args.output,
    )
    print(json.dumps(payload["metrics"], indent=2, sort_keys=True))
    return 0 if payload["baseline_complete"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
