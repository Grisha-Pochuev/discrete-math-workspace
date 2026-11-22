"""Bound candidate artifacts when the Third approach 2.0 runner exits.

Python imports ``sitecustomize`` automatically from PYTHONPATH.  The workflow
already launches runner.py with PYTHONPATH=third-approach-2.0, so this hook can
repair the historical orphan-file behaviour without changing the mathematical
search path.  Only the original runner process performs cleanup; forked worker
processes do nothing.
"""
from __future__ import annotations

import atexit
import gzip
import json
import math
import os
from pathlib import Path
import sys
from typing import Any

GLOBAL_PER_WORKER = 8
EXACT_PER_WORKER = 4
BASIN_PER_WORKER = 4
LINEAGE_PER_WORKER = 4


def prune_unkeyed(store: dict[str, dict[str, Any]], limit: int) -> None:
    if len(store) <= limit:
        return
    ranked = sorted(store.values(), key=lambda item: (item["score"], item["candidate_id"]))[:limit]
    store.clear()
    store.update((item["candidate_id"], item) for item in ranked)


def consider_unkeyed(
    store: dict[str, dict[str, Any]], record: dict[str, Any], limit: int
) -> None:
    previous = store.get(record["candidate_id"])
    if previous is None or record["score"] < previous["score"]:
        store[record["candidate_id"]] = record
    if len(store) > 2 * limit:
        prune_unkeyed(store, limit)


def prune_keyed(store: dict[str, dict[str, Any]], limit: int) -> None:
    if len(store) <= limit:
        return
    ranked = sorted(store.values(), key=lambda item: (item["score"], item["candidate_id"]))[:limit]
    store.clear()
    for item in ranked:
        store[item["selection_key"]] = item


def consider_keyed(
    store: dict[str, dict[str, Any]],
    key: str,
    record: dict[str, Any],
    limit: int,
) -> None:
    selected = dict(record)
    selected["selection_key"] = key
    previous = store.get(key)
    if previous is None or selected["score"] < previous["score"]:
        store[key] = selected
    if len(store) > 2 * limit:
        prune_keyed(store, limit)


def read_record(path: Path) -> dict[str, Any] | None:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as source:
            document = json.load(source)
        score = float(document["certificate_score"])
        candidate_id = str(document.get("candidate_id") or path.name)
    except Exception:
        return None
    if not math.isfinite(score) or not candidate_id:
        return None
    return {
        "candidate_id": candidate_id,
        "score": score,
        "path": path,
        "exact_verified": bool(document.get("exact_verified", False)),
        "basin": str(document.get("basin_fingerprint", "unknown")),
        "lineage": str(document.get("lineage_root", candidate_id)),
    }


def prune_worker(worker: Path) -> dict[str, int]:
    strongest: dict[str, dict[str, Any]] = {}
    exact: dict[str, dict[str, Any]] = {}
    basins: dict[str, dict[str, Any]] = {}
    lineages: dict[str, dict[str, Any]] = {}
    seen = 0
    malformed = 0

    for path in worker.glob("candidate-*.json.gz"):
        seen += 1
        record = read_record(path)
        if record is None:
            malformed += 1
            continue
        consider_unkeyed(strongest, record, GLOBAL_PER_WORKER)
        if record["exact_verified"]:
            consider_unkeyed(exact, record, EXACT_PER_WORKER)
        consider_keyed(basins, record["basin"], record, BASIN_PER_WORKER)
        consider_keyed(lineages, record["lineage"], record, LINEAGE_PER_WORKER)

    prune_unkeyed(strongest, GLOBAL_PER_WORKER)
    prune_unkeyed(exact, EXACT_PER_WORKER)
    prune_keyed(basins, BASIN_PER_WORKER)
    prune_keyed(lineages, LINEAGE_PER_WORKER)

    retained: set[Path] = set()
    for group in (strongest.values(), exact.values(), basins.values(), lineages.values()):
        retained.update(item["path"] for item in group)

    deleted = 0
    for path in worker.glob("candidate-*.json.gz"):
        if path not in retained:
            try:
                path.unlink()
                deleted += 1
            except FileNotFoundError:
                pass

    summary = {
        "seen_candidate_files": seen,
        "retained_candidate_files": len(retained),
        "deleted_candidate_files": deleted,
        "malformed_candidate_files": malformed,
    }
    (worker / "candidate-pruning.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def prune_output(output: Path) -> None:
    if not output.is_dir():
        return
    summaries = []
    for worker in sorted(output.glob("worker-*")):
        if worker.is_dir():
            summaries.append({"worker": worker.name, **prune_worker(worker)})
    if summaries:
        (output / "candidate-pruning-summary.json").write_text(
            json.dumps({"workers": summaries}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def runner_output_from_argv() -> Path | None:
    if Path(sys.argv[0]).name != "runner.py":
        return None
    try:
        index = sys.argv.index("--output")
        return Path(sys.argv[index + 1]).resolve()
    except (ValueError, IndexError):
        return None


_OWNER_PID = os.getpid()
_OUTPUT = runner_output_from_argv()


if _OUTPUT is not None:
    @atexit.register
    def _cleanup_runner_candidates() -> None:
        if os.getpid() == _OWNER_PID:
            prune_output(_OUTPUT)
