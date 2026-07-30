#!/usr/bin/env python3
"""Support generation and diagnostics for Second approach 2.0."""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np

LANE_COUNTS = {
    "fresh_independent": 30,
    "obstruction_boundary": 20,
    "novelty_far": 16,
    "legacy_control": 8,
    "precision_audit": 6,
}
KNOWN_OBSTRUCTIONS = {"inconsistent_signs", "mixed_monomial", "target_zero"}


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_legacy_model(repo: Path):
    return _load_module("second_approach_20_legacy_model", repo / "second-approach" / "model.py")


def load_exact_analyser(repo: Path):
    return _load_module("second_approach_20_exact", repo / "runs" / "2026-07-22-a" / "verify.py")


def load_bank(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with gzip.open(path, "rt", encoding="utf-8") as source:
            document = json.load(source)
        return [dict(item) for item in document.get("candidates", [])]
    except Exception:
        return []


def lane_for(job_id: int, worker_id: int) -> str:
    global_worker = int(job_id) * 4 + int(worker_id)
    if global_worker < 30:
        return "fresh_independent"
    if global_worker < 50:
        return "obstruction_boundary"
    if global_worker < 66:
        return "novelty_far"
    if global_worker < 74:
        return "legacy_control"
    if global_worker < 80:
        return "precision_audit"
    raise ValueError(f"global worker outside fixed 80-worker plan: {global_worker}")


def mask_from_candidate(candidate: dict[str, Any]) -> int:
    return int(str(candidate["support_mask_hex"]), 16)


def candidate_vector(model, candidate: dict[str, Any]) -> np.ndarray:
    x = np.zeros(model.NV, dtype=np.complex128)
    for variable, pair in zip(candidate.get("active_variables", []), candidate.get("active_weights", [])):
        x[int(variable)] = complex(float(pair[0]), float(pair[1]))
    return x


def hamming_distance(a: int, b: int) -> int:
    return int((int(a) ^ int(b)).bit_count())


def rank_weighted_parent(rng: np.random.Generator, candidates: list[dict[str, Any]], limit: int = 300):
    ranked = sorted(candidates, key=lambda item: float(item.get("max_error", 1e300)))[: max(1, limit)]
    if not ranked:
        return None
    weights = 1.0 / np.sqrt(np.arange(1, len(ranked) + 1, dtype=float))
    weights /= weights.sum()
    return ranked[int(rng.choice(len(ranked), p=weights))]


def fresh_support(model, rng: np.random.Generator) -> tuple[int, str]:
    choice = int(rng.integers(0, 5))
    if choice == 0:
        return model.ALL_MASK, "fresh_full"
    if choice == 1:
        return model.near_full_support(rng, int(rng.integers(5, 36))), "fresh_near_full"
    if choice == 2:
        target = int(rng.integers(31, 56))
        return model.random_dense_closed_support(rng, target), "fresh_closed_31_55"
    if choice == 3:
        target = int(rng.integers(56, 91))
        return model.random_dense_closed_support(rng, target), "fresh_closed_56_90"
    target = int(rng.integers(91, 126))
    return model.random_dense_closed_support(rng, target), "fresh_closed_91_125"


def exact_status(model, exact, mask: int) -> tuple[str, int]:
    counts = model.active_terms(mask).sum(axis=1)
    binary_rows = int(sum(int(counts[row]) == 2 for row in model.MIXED_ROWS))
    if binary_rows == 0:
        return "unresolved_no_binary_relations", binary_rows
    if mask.bit_count() <= 60 and binary_rows <= 24:
        try:
            return str(exact.analyse_support(mask)), binary_rows
        except Exception as exc:
            return f"exact_analyser_error:{type(exc).__name__}", binary_rows
    return "not_checked_dense", binary_rows


def obstruction_boundary_support(model, exact, rng: np.random.Generator) -> dict[str, Any]:
    fallback: dict[str, Any] | None = None
    for _ in range(18):
        target = int(rng.integers(27, 61))
        base = model.random_dense_closed_support(rng, target)
        status, binary_rows = exact_status(model, exact, base)
        fallback = {
            "mask": base,
            "family": "boundary_fallback",
            "boundary_source_obstruction": status,
            "boundary_edit_distance": 0,
            "binary_relation_rows_before": binary_rows,
        }
        if status not in KNOWN_OBSTRUCTIONS:
            continue
        missing = [k for k in range(model.NV) if not ((base >> k) & 1)]
        rng.shuffle(missing)
        max_add = min(len(missing), int(rng.integers(1, 6)))
        trial = base
        for edit_count, variable in enumerate(missing[:max_add], start=1):
            trial |= 1 << int(variable)
            trial_status, trial_binary = exact_status(model, exact, trial)
            if trial_status != status or edit_count == max_add:
                return {
                    "mask": trial,
                    "family": "obstruction_boundary",
                    "boundary_source_obstruction": status,
                    "boundary_result_status": trial_status,
                    "boundary_edit_distance": edit_count,
                    "binary_relation_rows_before": binary_rows,
                    "binary_relation_rows_after": trial_binary,
                }
    assert fallback is not None
    return fallback


def novelty_support(model, rng: np.random.Generator, references: list[int]) -> dict[str, Any]:
    best: tuple[int, int, str] | None = None
    sample_refs = references[:400]
    for _ in range(10):
        mask, family = fresh_support(model, rng)
        if sample_refs:
            distance = min(hamming_distance(mask, ref) for ref in sample_refs)
        else:
            distance = model.NV
        if best is None or distance > best[0]:
            best = (distance, mask, family)
    assert best is not None
    return {
        "mask": best[1],
        "family": "novelty_far_" + best[2],
        "nearest_bank_hamming_distance": best[0],
    }


def parent_payload(model, parent: dict[str, Any]) -> dict[str, Any]:
    return {
        "parent_candidate_id": str(parent.get("candidate_id", "unknown")),
        "parent_max_error": float(parent.get("max_error", 1e300)),
        "lineage_root": str(parent.get("lineage_root") or parent.get("candidate_id", "unknown")),
        "initial_x": candidate_vector(model, parent),
    }


def choose_support(
    model,
    exact,
    rng: np.random.Generator,
    lane: str,
    legacy_bank: list[dict[str, Any]],
    new_bank: list[dict[str, Any]],
) -> dict[str, Any]:
    references = [mask_from_candidate(item) for item in (legacy_bank[:200] + new_bank[:400]) if item.get("support_mask_hex")]
    if lane == "fresh_independent":
        mask, family = fresh_support(model, rng)
        return {"mask": mask, "family": family, "initial_x": None, "lineage_root": None}
    if lane == "obstruction_boundary":
        result = obstruction_boundary_support(model, exact, rng)
        result.update({"initial_x": None, "lineage_root": None})
        return result
    if lane == "novelty_far":
        result = novelty_support(model, rng, references)
        result.update({"initial_x": None, "lineage_root": None})
        return result
    if lane == "legacy_control":
        parent = rank_weighted_parent(rng, legacy_bank, limit=100)
        if parent is None:
            mask, family = fresh_support(model, rng)
            return {"mask": mask, "family": "legacy_control_fallback_" + family, "initial_x": None, "lineage_root": None}
        result = parent_payload(model, parent)
        result.update({
            "mask": model.mutate_seed_support(mask_from_candidate(parent), rng),
            "family": "legacy_control_mutation",
            "legacy_rooted": True,
        })
        return result
    if lane == "precision_audit":
        pool = new_bank if new_bank else legacy_bank
        parent = rank_weighted_parent(rng, pool, limit=200)
        if parent is None:
            mask, family = fresh_support(model, rng)
            return {"mask": mask, "family": "precision_audit_fallback_" + family, "initial_x": None, "lineage_root": None}
        result = parent_payload(model, parent)
        root = str(result["lineage_root"])
        result.update({
            "mask": mask_from_candidate(parent),
            "family": "precision_audit",
            "legacy_rooted": bool(parent.get("legacy_rooted", False) or root.startswith("r")),
        })
        return result
    raise ValueError(f"unknown lane {lane}")


def residual_signature(model, x: np.ndarray, limit: int = 12) -> tuple[list[dict[str, Any]], str]:
    amp = model.amplitudes(x)
    errors = np.abs(amp - model.TARGET)
    mixed = [(int(row), float(errors[int(row)])) for row in model.MIXED_ROWS]
    mixed.sort(key=lambda item: item[1], reverse=True)
    top = []
    for row, value in mixed[:limit]:
        top.append({
            "row": row,
            "colouring": [int(v) for v in model.COLOURINGS[row]],
            "abs_error": value,
        })
    bucket = tuple(item["row"] for item in top[:6])
    fingerprint = hashlib.sha256(repr(bucket).encode("utf-8")).hexdigest()[:20]
    return top, fingerprint


def support_fingerprint(mask: int) -> str:
    return hashlib.sha256(f"{int(mask):x}".encode("ascii")).hexdigest()[:20]
