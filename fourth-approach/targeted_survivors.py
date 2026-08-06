#!/usr/bin/env python3
"""Targeted higher-degree exact-certificate tests for Run 006.

The run uses a compact, diversity-aware set of Run-005 hard survivors.  Every
worker keeps one numerical candidate support fixed and searches a precisely
recorded family of coefficient-space Nullstellensatz certificates with
multiplier degrees up to five.  Numerical residuals are only leads.  A case is
called closed only after rational reconstruction and an independent exact
polynomial-identity check on the unchanged candidate support.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import gzip
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import sys
import time
from typing import Any, Iterable

import numpy as np
from scipy.sparse.linalg import lsqr


GROUP_LIMITS = {
    "old_pool": 10,
    "legacy_2_0": 20,
    "independent_2_0": 30,
}
EXPECTED_SELECTED = sum(GROUP_LIMITS.values())
MONO_ROWS = (0, 364, 728)


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


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def modules(repo: Path):
    cert = load_module("run006_certificate", repo / "third-approach-2.0" / "certificate.py")
    bridge = load_module("run006_bridge", repo / "fourth-approach" / "bridge_second.py")
    return cert, bridge


def raw_bank_map(path: Path, source_kind: str) -> dict[str, dict[str, Any]]:
    document = read_gzip_json(path)
    result: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(document.get("candidates", [])):
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        identifier = str(item.get("candidate_id") or f"index-{index}")
        result[f"{source_kind}::{identifier}"] = item
    return result


def diversity_select(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    ranked = sorted(
        items,
        key=lambda item: (
            float(item.get("max_error", float("inf"))),
            int(item.get("nearest_exact_distance", 10**9)),
            str(item.get("candidate_key")),
        ),
    )
    selected: list[dict[str, Any]] = []
    used_supports: set[str] = set()
    used_lineages: set[str] = set()

    for item in ranked:
        support = str(item.get("canonical_support_id", ""))
        lineage = str(item.get("lineage_root") or item.get("candidate_id") or "")
        if support in used_supports:
            continue
        if lineage and lineage in used_lineages:
            continue
        selected.append(item)
        used_supports.add(support)
        if lineage:
            used_lineages.add(lineage)
        if len(selected) >= limit:
            return selected

    for item in ranked:
        key = str(item.get("candidate_key"))
        if any(str(chosen.get("candidate_key")) == key for chosen in selected):
            continue
        selected.append(item)
        if len(selected) >= limit:
            break
    return selected


def prepare_selection(
    repo: Path,
    hard_survivors: Path,
    old_bank: Path,
    second20_bank: Path,
) -> dict[str, Any]:
    _cert, bridge = modules(repo)
    if hard_survivors.suffix == ".gz":
        hard = read_gzip_json(hard_survivors)
    else:
        hard = json.loads(hard_survivors.read_text(encoding="utf-8"))
    survivors = list(hard.get("records", hard.get("survivors", [])))
    group_sizes = {
        group: sum(str(item.get("group", "")) == group for item in survivors)
        for group in GROUP_LIMITS
    }
    if any(group_sizes[group] < limit for group, limit in GROUP_LIMITS.items()):
        full_records_path = hard_survivors.with_name("bridge-records.json.gz")
        if not full_records_path.exists():
            raise ValueError(
                f"compact survivor display is incomplete {group_sizes} and full records are missing: {full_records_path}"
            )
        full_document = read_gzip_json(full_records_path)
        survivors = list(full_document.get("records", []))
    old_map = raw_bank_map(old_bank, "old_seed_bank")
    second_map = raw_bank_map(second20_bank, "second_approach_2_0")
    full_map = {**old_map, **second_map}

    grouped: dict[str, list[dict[str, Any]]] = {key: [] for key in GROUP_LIMITS}
    for survivor in survivors:
        group = str(survivor.get("group", ""))
        if group in grouped:
            grouped[group].append(dict(survivor))

    chosen: list[dict[str, Any]] = []
    for group, limit in GROUP_LIMITS.items():
        group_selection = diversity_select(grouped[group], limit)
        if len(group_selection) != limit:
            raise ValueError(f"group {group} has only {len(group_selection)} selectable survivors")
        chosen.extend(group_selection)

    selected_records = []
    for slot, survivor in enumerate(chosen):
        key = str(survivor["candidate_key"])
        raw = full_map.get(key)
        if raw is None:
            raise ValueError(f"missing raw candidate for {key}")
        mask = bridge.candidate_mask(raw)
        support = list(bridge.values_from_mask(mask))
        if not all(value > 0 for value in bridge.mono_matching_counts(support)):
            raise ValueError(f"selected candidate lacks all monochromatic targets: {key}")
        score = float(survivor.get("max_error", raw.get("max_error", float("inf"))))
        if not math.isfinite(score):
            raise ValueError(f"non-finite score for {key}")
        selected_records.append({
            "slot": slot,
            "candidate_key": key,
            "candidate_id": str(survivor["candidate_id"]),
            "group": str(survivor["group"]),
            "lane": survivor.get("lane"),
            "lineage_root": survivor.get("lineage_root"),
            "max_error": score,
            "canonical_support_id": str(survivor.get("canonical_support_id", "")),
            "nearest_exact_distance": int(survivor.get("nearest_exact_distance", -1)),
            "support_variables": support,
            "support_mask_hex": hex(mask),
            "support_size": len(support),
            "source_kind": "old_seed_bank" if key.startswith("old_seed_bank::") else "second_approach_2_0",
        })

    if len(selected_records) != EXPECTED_SELECTED:
        raise ValueError("selection size mismatch")
    group_counts = {
        group: sum(1 for item in selected_records if item["group"] == group)
        for group in GROUP_LIMITS
    }
    payload = {
        "schema_version": 1,
        "task": "stage6_prepare_targeted_hard_survivors",
        "selection_policy": {
            "group_limits": GROUP_LIMITS,
            "ordering": "best residual first with canonical-support and lineage diversity before score-only fill",
        },
        "source_run_005": "fourth-approach/runs/run-005-31034878944",
        "selected_count": len(selected_records),
        "group_counts": group_counts,
        "selected": selected_records,
    }
    payload["selection_digest"] = stable_hash(payload)
    return payload


PROFILES: tuple[dict[str, Any], ...] = (
    {
        "name": "degree3_expanded",
        "equation_limit": 128,
        "feature_counts": {1: 36, 2: 72, 3: 112},
        "max_iterations": 5000,
    },
    {
        "name": "degree4_sparse",
        "equation_limit": 92,
        "feature_counts": {1: 28, 2: 52, 3: 72, 4: 48},
        "max_iterations": 5500,
    },
    {
        "name": "degree4_wide",
        "equation_limit": 116,
        "feature_counts": {1: 32, 2: 64, 3: 88, 4: 72},
        "max_iterations": 6000,
    },
    {
        "name": "degree5_sparse",
        "equation_limit": 84,
        "feature_counts": {1: 24, 2: 44, 3: 56, 4: 44, 5: 28},
        "max_iterations": 6500,
    },
)


def random_monomials(
    rng: np.random.Generator,
    support: np.ndarray,
    degree: int,
    count: int,
    existing: set[tuple[int, ...]],
) -> list[tuple[int, ...]]:
    result: list[tuple[int, ...]] = []
    values = np.asarray(support, dtype=np.int16)
    attempts = 0
    limit = max(200, count * 80)
    while len(result) < count and attempts < limit:
        feature = tuple(sorted(int(value) for value in rng.choice(values, size=degree, replace=True)))
        attempts += 1
        if feature not in existing:
            existing.add(feature)
            result.append(feature)
    return result


def choose_features(
    rng: np.random.Generator,
    support: np.ndarray,
    counts: dict[int, int],
) -> list[tuple[int, ...]]:
    features: list[tuple[int, ...]] = [tuple()]
    existing = {tuple()}
    for degree in sorted(counts):
        features.extend(random_monomials(rng, support, degree, int(counts[degree]), existing))
    return sorted(features, key=lambda item: (len(item), item))


def choose_rows(cert, rng: np.random.Generator, support: np.ndarray, limit: int) -> np.ndarray:
    rows, term_counts = cert.active_rows(support)
    mono = [int(row) for row in MONO_ROWS]
    mixed = [int(row) for row in rows if int(row) not in MONO_ROWS]
    rng.shuffle(mixed)
    mixed.sort(key=lambda row: (int(term_counts[row]), float(rng.random())))
    selected = mono + mixed[: max(0, int(limit) - len(mono))]
    return np.asarray(selected, dtype=np.int32)


def rational_terms(
    descriptors: list[tuple[int, tuple[int, ...]]],
    coefficients: list[list[list[int]]],
) -> list[dict[str, Any]]:
    terms = []
    for (row, feature), pair in zip(descriptors, coefficients):
        real = Fraction(int(pair[0][0]), int(pair[0][1]))
        imag = Fraction(int(pair[1][0]), int(pair[1][1]))
        if real == 0 and imag == 0:
            continue
        terms.append({
            "row": int(row),
            "feature": tuple(int(value) for value in feature),
            "real": real,
            "imag": imag,
        })
    return terms


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
    return result


def try_exact_reconstruction(
    cert,
    bridge,
    support: np.ndarray,
    matrix,
    target: np.ndarray,
    descriptors: list[tuple[int, tuple[int, ...]]],
    solution: np.ndarray,
) -> tuple[list[dict[str, Any]] | None, dict[str, Any]]:
    attempts = 0
    candidates: list[tuple[Any, list[tuple[int, tuple[int, ...]]], str]] = []
    candidates.append((matrix, descriptors, "full"))

    absolute = np.abs(solution)
    orders = np.argsort(-absolute)
    for cap in (96, 192):
        if cap >= len(solution):
            continue
        indices = np.sort(orders[:cap])
        submatrix = matrix[:, indices]
        if submatrix.shape[1] == 0:
            continue
        candidates.append((submatrix, [descriptors[int(index)] for index in indices], f"top-{cap}"))

    best_meta: dict[str, Any] = {"reconstruction_attempts": 0}
    for candidate_matrix, candidate_descriptors, kind in candidates:
        solved = lsqr(
            candidate_matrix,
            target,
            atol=1e-13,
            btol=1e-13,
            iter_lim=8000,
            show=False,
        )
        coefficients = np.asarray(solved[0], dtype=float).astype(np.complex128)
        for threshold in (0.0, 1e-11):
            trial = coefficients.copy()
            if threshold:
                trial[np.abs(trial) < threshold] = 0.0
            for denominator in (10_000, 100_000):
                attempts += 1
                exact, rational = cert.exact_rational_verification(
                    candidate_matrix,
                    target,
                    trial,
                    denominator_limit=denominator,
                )
                if not exact or rational is None:
                    continue
                terms = rational_terms(candidate_descriptors, rational)
                valid, error = bridge.verify_sparse_certificate(
                    [int(value) for value in support],
                    terms,
                )
                if valid:
                    return terms, {
                        "reconstruction_attempts": attempts,
                        "reconstruction_kind": kind,
                        "denominator_limit": denominator,
                        "threshold": threshold,
                        "nonzero_terms": len(terms),
                    }
                best_meta["last_independent_error"] = error
    best_meta["reconstruction_attempts"] = attempts
    return None, best_meta


def search_attempt(
    cert,
    bridge,
    rng: np.random.Generator,
    selected: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    support = np.asarray(selected["support_variables"], dtype=np.int16)
    row_limit = int(profile["equation_limit"]) + int(rng.integers(-8, 9))
    row_limit = max(24, row_limit)
    rows = choose_rows(cert, rng, support, row_limit)
    counts = {
        int(degree): max(0, int(count) + int(rng.integers(-4, 5)))
        for degree, count in profile["feature_counts"].items()
    }
    features = choose_features(rng, support, counts)
    matrix, target, monomials, descriptors = cert.coefficient_system(support, rows, features)
    if matrix.shape[0] == 0 or matrix.shape[1] == 0:
        raise RuntimeError("empty coefficient system")
    solution_info = lsqr(
        matrix,
        target,
        atol=1e-12,
        btol=1e-12,
        iter_lim=int(profile["max_iterations"]),
        show=False,
    )
    coefficients = np.asarray(solution_info[0], dtype=float).astype(np.complex128)
    residual = matrix @ coefficients.real - target
    residual_abs = np.abs(residual)
    maximum = float(np.max(residual_abs))
    rms = float(np.sqrt(np.mean(residual_abs**2)))
    exact_terms = None
    reconstruction = {"reconstruction_attempts": 0}
    if maximum < 1e-9:
        exact_terms, reconstruction = try_exact_reconstruction(
            cert, bridge, support, matrix, target, descriptors, coefficients
        )
    return {
        "profile": str(profile["name"]),
        "equation_rows": len(rows),
        "features": len(features),
        "max_multiplier_degree": max((len(feature) for feature in features), default=0),
        "feature_degree_counts": {
            str(degree): sum(1 for feature in features if len(feature) == degree)
            for degree in range(6)
        },
        "matrix_rows": int(matrix.shape[0]),
        "matrix_columns": int(matrix.shape[1]),
        "matrix_nonzeros": int(matrix.nnz),
        "polynomial_monomials": len(monomials),
        "lsqr_stop_code": int(solution_info[1]),
        "lsqr_iterations": int(solution_info[2]),
        "coefficient_rms": rms,
        "coefficient_max": maximum,
        "exact_verified": exact_terms is not None,
        "exact_terms": None if exact_terms is None else serialize_terms(exact_terms),
        **reconstruction,
    }


def worker_run(
    repo: Path,
    selection_path: Path,
    slot: int,
    seconds: int,
    max_attempts: int,
    output: Path,
) -> dict[str, Any]:
    cert, bridge = modules(repo)
    selection = read_gzip_json(selection_path)
    selected_items = list(selection.get("selected", []))
    if not 0 <= slot < len(selected_items):
        raise ValueError(f"slot {slot} outside selection")
    selected = dict(selected_items[slot])
    profile = PROFILES[slot % len(PROFILES)]
    rng = np.random.default_rng(6_000_011 + slot)
    started = time.time()
    deadline = started + max(60, int(seconds) - 180)
    attempts = 0
    best: dict[str, Any] | None = None
    exact: dict[str, Any] | None = None
    errors: list[str] = []

    def checkpoint() -> dict[str, Any]:
        payload = {
            "schema_version": 1,
            "task": "stage6_targeted_hard_survivors",
            "selection_digest": str(selection["selection_digest"]),
            "slot": slot,
            "selected": selected,
            "profile": profile,
            "attempts": attempts,
            "best": best,
            "exact": exact,
            "errors": errors[-20:],
            "baseline_complete": attempts > 0,
            "finished": exact is not None or time.time() >= deadline or (max_attempts > 0 and attempts >= max_attempts),
        }
        write_gzip_json(output, payload)
        return payload

    while time.time() < deadline and (max_attempts <= 0 or attempts < max_attempts):
        attempts += 1
        try:
            result = search_attempt(cert, bridge, rng, selected, profile)
            rank = (
                0 if result["exact_verified"] else 1,
                int(result.get("nonzero_terms", 10**9)),
                float(result["coefficient_max"]),
                float(result["coefficient_rms"]),
            )
            if best is None:
                best = result
            else:
                old_rank = (
                    0 if best["exact_verified"] else 1,
                    int(best.get("nonzero_terms", 10**9)),
                    float(best["coefficient_max"]),
                    float(best["coefficient_rms"]),
                )
                if rank < old_rank:
                    best = result
            if result["exact_verified"]:
                exact = result
                checkpoint()
                break
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
        checkpoint()
    return checkpoint()


def self_test() -> None:
    dummy = [
        {
            "candidate_key": f"k-{index}",
            "candidate_id": f"c-{index}",
            "group": "old_pool",
            "max_error": 1e-5 + index * 1e-7,
            "nearest_exact_distance": 10 + index,
            "canonical_support_id": f"s-{index % 4}",
            "lineage_root": f"l-{index % 5}",
        }
        for index in range(20)
    ]
    chosen = diversity_select(dummy, 10)
    assert len(chosen) == 10
    rng = np.random.default_rng(123)
    support = np.arange(12, dtype=np.int16)
    features = choose_features(rng, support, {1: 4, 2: 4, 4: 3, 5: 2})
    assert tuple() in features
    assert max(len(feature) for feature in features) == 5
    assert len({feature for feature in features}) == len(features)
    print(json.dumps({"self_test": "ok", "selected": len(chosen), "features": len(features)}))


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare")
    prepare.add_argument("--repo", type=Path, default=Path("."))
    prepare.add_argument("--hard-survivors", type=Path, required=True)
    prepare.add_argument("--old-bank", type=Path, required=True)
    prepare.add_argument("--second20-bank", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)

    worker = sub.add_parser("worker")
    worker.add_argument("--repo", type=Path, default=Path("."))
    worker.add_argument("--selection", type=Path, required=True)
    worker.add_argument("--slot", type=int, required=True)
    worker.add_argument("--seconds", type=int, default=20400)
    worker.add_argument("--max-attempts", type=int, default=0)
    worker.add_argument("--output", type=Path, required=True)

    sub.add_parser("self-test")
    args = parser.parse_args()

    if args.command == "self-test":
        self_test()
        return 0
    if args.command == "prepare":
        payload = prepare_selection(
            args.repo.resolve(),
            args.hard_survivors.resolve(),
            args.old_bank.resolve(),
            args.second20_bank.resolve(),
        )
        write_gzip_json(args.output.resolve(), payload)
        print(json.dumps({
            "selected_count": payload["selected_count"],
            "group_counts": payload["group_counts"],
            "selection_digest": payload["selection_digest"],
        }, indent=2, sort_keys=True))
        return 0
    if args.command == "worker":
        payload = worker_run(
            args.repo.resolve(),
            args.selection.resolve(),
            args.slot,
            args.seconds,
            args.max_attempts,
            args.output.resolve(),
        )
        print(json.dumps({
            "slot": payload["slot"],
            "attempts": payload["attempts"],
            "exact": payload["exact"] is not None,
            "baseline_complete": payload["baseline_complete"],
        }, indent=2, sort_keys=True))
        return 0 if payload["baseline_complete"] else 3
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
