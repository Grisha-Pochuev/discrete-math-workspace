#!/usr/bin/env python3
"""Support generation, lineage selection, and diagnostics for Second approach 2.0."""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import argparse
from collections import Counter, defaultdict
import multiprocessing as mp
import os
import platform
import signal
import socket
import statistics
import sys
import time
import traceback
from pathlib import Path
from typing import Any

import numpy as np


engine = sys.modules[__name__]

LANE_PLANS: dict[int, dict[str, int]] = {
    1: {
        "fresh_independent": 30,
        "obstruction_boundary": 20,
        "novelty_far": 16,
        "legacy_control": 8,
        "precision_audit": 6,
    },
    2: {
        # Keep broad exploration, but devote the largest share to inherited
        # development of several genuinely independent lineages.
        "fresh_independent": 12,
        "obstruction_boundary": 8,
        "novelty_far": 8,
        "independent_precision": 20,
        "independent_mutation": 16,
        "legacy_adaptive": 8,
        "legacy_escape": 4,
        "legacy_precision": 4,
    },
}
LANE_COUNTS = LANE_PLANS[2]
ALLOWED_LEGACY_STRATEGIES = {
    "micro_polish",
    "support_mutation",
    "wide_restart",
    "bound_expansion",
    "residual_escape",
}
ALLOWED_INDEPENDENT_STRATEGIES = {
    "balanced",
    "precision_heavy",
    "mutation_heavy",
    "escape_heavy",
}
FRESH_INDEPENDENT_LANES = {
    "fresh_independent",
    "obstruction_boundary",
    "novelty_far",
}
INHERITED_INDEPENDENT_LANES = {
    "independent_precision",
    "independent_mutation",
}
INDEPENDENT_LANES = FRESH_INDEPENDENT_LANES | INHERITED_INDEPENDENT_LANES
LEGACY_LANES = {
    "legacy_control",
    "precision_audit",
    "legacy_adaptive",
    "legacy_escape",
    "legacy_precision",
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
    return _load_module(
        "second_approach_20_legacy_model", repo / "second-approach" / "model.py"
    )


def load_exact_analyser(repo: Path):
    return _load_module(
        "second_approach_20_exact", repo / "runs" / "2026-07-22-a" / "verify.py"
    )


def load_bank(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with gzip.open(path, "rt", encoding="utf-8") as source:
            document = json.load(source)
        return [dict(item) for item in document.get("candidates", [])]
    except Exception:
        return []


def lane_for(job_id: int, worker_id: int, lane_plan_version: int = 2) -> str:
    plan = LANE_PLANS.get(int(lane_plan_version))
    if plan is None:
        raise ValueError(f"unknown lane plan version: {lane_plan_version}")
    global_worker = int(job_id) * 4 + int(worker_id)
    start = 0
    for lane, count in plan.items():
        stop = start + int(count)
        if start <= global_worker < stop:
            return lane
        start = stop
    raise ValueError(
        f"global worker outside {sum(plan.values())}-worker plan: {global_worker}"
    )


def mask_from_candidate(candidate: dict[str, Any]) -> int:
    return int(str(candidate["support_mask_hex"]), 16)


def candidate_vector(model, candidate: dict[str, Any]) -> np.ndarray:
    x = np.zeros(model.NV, dtype=np.complex128)
    for variable, pair in zip(
        candidate.get("active_variables", []), candidate.get("active_weights", [])
    ):
        x[int(variable)] = complex(float(pair[0]), float(pair[1]))
    return x


def hamming_distance(a: int, b: int) -> int:
    return int((int(a) ^ int(b)).bit_count())


def candidate_lineage_root(candidate: dict[str, Any]) -> str:
    return str(
        candidate.get("lineage_root")
        or candidate.get("candidate_id")
        or "unknown-lineage"
    )


def is_independent_candidate(candidate: dict[str, Any]) -> bool:
    """Recognize independent origin even after later inherited refinement."""
    if bool(candidate.get("legacy_rooted", False)):
        return False
    if str(candidate.get("lineage_origin", "")) == "independent":
        return True
    lane = str(candidate.get("lane", ""))
    if lane in INDEPENDENT_LANES:
        return True
    root = candidate_lineage_root(candidate)
    # Historical 2.0 independent roots use the sa20 prefix. This recovers
    # independent descendants created by the old precision_audit lane.
    return root.startswith("sa20-")


def _candidate_score(candidate: dict[str, Any]) -> float:
    score = float(candidate.get("max_error", 1e300))
    depth = int(candidate.get("lineage_depth", 0) or 0)
    gain = float(candidate.get("parent_improvement_fraction", 1.0) or 0.0)
    # Avoid spending every inherited worker forever on a lineage whose last
    # several generations are deep and almost stationary, while preserving it
    # in the bank for later tactics.
    if depth >= 6 and gain < 0.001:
        score *= 1.25
    elif depth >= 4 and gain < 0.002:
        score *= 1.08
    return score


def rank_weighted_parent(
    rng: np.random.Generator,
    candidates: list[dict[str, Any]],
    limit: int = 300,
) -> dict[str, Any] | None:
    ranked = sorted(candidates, key=_candidate_score)[: max(1, int(limit))]
    if not ranked:
        return None
    weights = 1.0 / np.sqrt(np.arange(1, len(ranked) + 1, dtype=float))
    weights /= weights.sum()
    return ranked[int(rng.choice(len(ranked), p=weights))]


def diverse_lineage_representatives(
    candidates: list[dict[str, Any]],
    *,
    independent_only: bool,
    limit: int,
) -> list[dict[str, Any]]:
    filtered = [
        item
        for item in candidates
        if is_independent_candidate(item) is bool(independent_only)
        and item.get("support_mask_hex")
        and item.get("active_variables") is not None
    ]
    ranked = sorted(filtered, key=_candidate_score)
    selected: list[dict[str, Any]] = []
    seen_lineages: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()

    # First retain one strong representative from each lineage.
    for item in ranked:
        root = candidate_lineage_root(item)
        if root in seen_lineages:
            continue
        selected.append(item)
        seen_lineages.add(root)
        seen_pairs.add(
            (
                str(item.get("support_fingerprint", item.get("support_mask_hex"))),
                str(item.get("residual_basin_fingerprint", "unknown")),
            )
        )
        if len(selected) >= limit:
            return selected

    # Then admit structurally distinct alternatives from good lineages.
    for item in ranked:
        pair = (
            str(item.get("support_fingerprint", item.get("support_mask_hex"))),
            str(item.get("residual_basin_fingerprint", "unknown")),
        )
        if pair in seen_pairs:
            continue
        selected.append(item)
        seen_pairs.add(pair)
        if len(selected) >= limit:
            break
    return selected


def choose_diverse_parent(
    rng: np.random.Generator,
    candidates: list[dict[str, Any]],
    *,
    independent_only: bool,
    global_worker_id: int,
    run_index: int,
    attempt: int,
    limit: int = 96,
) -> dict[str, Any] | None:
    representatives = diverse_lineage_representatives(
        candidates, independent_only=independent_only, limit=limit
    )
    if not representatives:
        return None
    focus_count = min(32, len(representatives))
