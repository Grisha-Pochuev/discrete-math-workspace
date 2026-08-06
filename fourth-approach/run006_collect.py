#!/usr/bin/env python3
"""Aggregate and independently verify Fourth approach Run 006."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any


APPROACH = "fourth-approach-obstruction-guided-exact-synthesis"
EXPECTED_WORKERS = 60


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def deserialize_terms(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from fractions import Fraction

    return [
        {
            "row": int(item["row"]),
            "feature": tuple(int(value) for value in item.get("feature", [])),
            "real": Fraction(int(item["real"][0]), int(item["real"][1])),
            "imag": Fraction(int(item["imag"][0]), int(item["imag"][1])),
        }
        for item in items
    ]


def collect_worker_files(root: Path) -> list[Path]:
    return sorted(root.rglob("worker-*.json.gz"))


def update_state(repo: Path, summary: dict[str, Any]) -> None:
    control_path = repo / "fourth-approach" / "control.json"
    launch_path = repo / "fourth-approach" / "launch.json"
    control = read_json(control_path)
    history = list(control.get("run_history", []))
    history.append({
        "run_id": int(summary["run_id"]),
        "run_index": 6,
        "task": summary["task"],
        "accepted": bool(summary["accepted"]),
        "metrics": summary["metrics"],
    })
    control.update(
        completed_runs=int(control.get("completed_runs", 0)) + 1,
        current_stage=7,
        current_stage_name="gpt_sol_compact_handoff",
        last_run_id=int(summary["run_id"]),
        last_run_index=6,
        last_run_accepted=bool(summary["accepted"]),
        next_run_index=7,
        next_task="stage7_gpt_sol_handoff",
        next_spec_path="fourth-approach/run-specs/run-007-stage7-gpt-sol-handoff.json",
        recommended_next_action="review_exact_closures_and_compact_handoff_before_any_new_long_run",
        scientific_stopping_rule="manual GPT-5.6 Sol review before additional compute",
        minimum_free_concurrency_slots=5,
        run_history=history,
    )
    atomic_json(control_path, control)
    atomic_json(launch_path, {
        "schema_version": 1,
        "enabled": False,
        "run_index": 6,
        "task": "stage6_targeted_hard_survivors",
        "spec_path": "fourth-approach/run-specs/run-006-stage6-targeted-hard-survivors.json",
        "jobs": 15,
        "minimum_jobs": 15,
        "runtime_seconds": 20400,
        "max_attempts": 0,
        "nonce": f"fourth-run-006-completed-{summary['run_id']}",
    })


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()

    repo = args.repo.resolve()
    artifacts = args.artifacts.resolve()
    selection = read_gzip_json(args.selection.resolve())
    selected = list(selection.get("selected", []))
    selection_digest = str(selection.get("selection_digest", ""))
    if len(selected) != EXPECTED_WORKERS:
        raise SystemExit(f"selection has {len(selected)} candidates, expected {EXPECTED_WORKERS}")

    bridge = load_module("run006_bridge_verify", repo / "fourth-approach" / "bridge_second.py")
    worker_paths = collect_worker_files(artifacts)
    workers: dict[int, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []

    for path in worker_paths:
        try:
            payload = read_gzip_json(path)
            slot = int(payload["slot"])
            if slot in workers:
                raise ValueError(f"duplicate slot {slot}")
            if str(payload.get("selection_digest")) != selection_digest:
                raise ValueError(f"selection digest mismatch for slot {slot}")
            if payload.get("baseline_complete") is not True:
                raise ValueError(f"slot {slot} has no completed attempt")
            expected = selected[slot]
            actual = payload.get("selected", {})
            if str(actual.get("candidate_key")) != str(expected.get("candidate_key")):
                raise ValueError(f"candidate mismatch for slot {slot}")
            exact = payload.get("exact")
            if exact is not None:
                terms = deserialize_terms(list(exact.get("exact_terms") or []))
                valid, error = bridge.verify_sparse_certificate(
                    [int(value) for value in expected["support_variables"]],
                    terms,
                )
                if not valid:
                    raise ValueError(f"independent exact verification failed for slot {slot}: {error}")
                exact["collector_independently_verified"] = True
            workers[slot] = payload
        except Exception as exc:
            errors.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})

    missing_slots = sorted(set(range(EXPECTED_WORKERS)) - set(workers))
    if missing_slots:
        errors.append({"missing_slots": missing_slots})

    records = []
    for slot in sorted(workers):
        payload = workers[slot]
        selected_record = dict(payload["selected"])
        best = payload.get("best")
        exact = payload.get("exact")
        records.append({
            **selected_record,
            "slot": slot,
            "profile": str(payload.get("profile", {}).get("name", "unknown")),
            "attempts": int(payload.get("attempts", 0)),
            "best": best,
            "exact_closed": exact is not None,
            "exact": exact,
            "worker_errors": list(payload.get("errors", [])),
        })

    groups: dict[str, dict[str, Any]] = {}
    for group in ("old_pool", "legacy_2_0", "independent_2_0"):
        group_records = [record for record in records if record["group"] == group]
        exact_records = [record for record in group_records if record["exact_closed"]]
        survivors = [record for record in group_records if not record["exact_closed"]]
        groups[group] = {
            "selected": len(group_records),
            "exactly_closed": len(exact_records),
            "survivors": len(survivors),
            "best_input_max_error": min((float(record["max_error"]) for record in group_records), default=None),
            "best_survivor_max_error": min((float(record["max_error"]) for record in survivors), default=None),
            "profiles": {
                profile: sum(1 for record in group_records if record["profile"] == profile)
                for profile in sorted({record["profile"] for record in group_records})
            },
        }

    exact_closures = [
        {
            "slot": record["slot"],
            "candidate_key": record["candidate_key"],
            "candidate_id": record["candidate_id"],
            "group": record["group"],
            "max_error": record["max_error"],
            "support_size": record["support_size"],
            "profile": record["profile"],
            "attempts": record["attempts"],
            "exact": record["exact"],
        }
        for record in records
        if record["exact_closed"]
    ]
    survivors = [
        {
            "slot": record["slot"],
            "candidate_key": record["candidate_key"],
            "candidate_id": record["candidate_id"],
            "group": record["group"],
            "lane": record.get("lane"),
            "lineage_root": record.get("lineage_root"),
            "max_error": record["max_error"],
            "support_size": record["support_size"],
            "nearest_exact_distance": record["nearest_exact_distance"],
            "profile": record["profile"],
            "attempts": record["attempts"],
            "best": record["best"],
        }
        for record in records
        if not record["exact_closed"]
    ]
    survivors.sort(key=lambda item: (item["group"], float(item["max_error"]), item["candidate_key"]))

    metrics = {
        "jobs_configured": 15,
        "workers_expected": EXPECTED_WORKERS,
        "workers_present": len(workers),
        "selected_candidates": len(selected),
        "exactly_closed": len(exact_closures),
        "survivors": len(survivors),
        "invalid_or_missing_workers": len(errors),
        "groups": groups,
        "total_attempts": sum(int(record["attempts"]) for record in records),
        "maximum_tested_multiplier_degree": max(
            (
                int(record.get("best", {}).get("max_multiplier_degree", 0))
                for record in records
                if record.get("best")
            ),
            default=0,
        ),
    }
    accepted = len(workers) == EXPECTED_WORKERS and not errors and len(records) == len(selected)

    run_dir = repo / "fourth-approach" / "runs" / f"run-006-{args.run_id}"
    if run_dir.exists():
        existing = read_json(run_dir / "summary.json")
        if int(existing.get("run_id", -1)) == args.run_id:
            print(json.dumps(existing, indent=2, sort_keys=True))
            return 0 if existing.get("accepted") else 3
        raise SystemExit(f"refusing to overwrite {run_dir}")
    run_dir.mkdir(parents=True)

    write_gzip_json(run_dir / "targeted-results.json.gz", {
        "schema_version": 1,
        "task": "stage6_targeted_hard_survivors",
        "selection_digest": selection_digest,
        "records": records,
        "worker_errors": errors,
    })
    atomic_json(run_dir / "exact-closures.json", {
        "schema_version": 1,
        "scope": "independently verified exact certificates on unchanged selected candidate supports",
        "closures": exact_closures,
    })
    atomic_json(run_dir / "survivors.json", {
        "schema_version": 1,
        "scope": "survived only the precisely recorded Run-006 certificate profiles; not counterexamples",
        "survivors": survivors,
    })
    handoff = {
        "schema_version": 1,
        "purpose": "compact evidence package for GPT-5.6 Sol",
        "exact_closures": exact_closures[:20],
        "strongest_survivors_by_group": {
            group: [item for item in survivors if item["group"] == group][:10]
            for group in ("old_pool", "legacy_2_0", "independent_2_0")
        },
        "interpretation": (
            "A survivor means only that no exact certificate was found in the recorded "
            "degree-3/4/5 randomized descriptor profiles during this bounded run."
        ),
    }
    atomic_json(run_dir / "gpt-sol-handoff.json", handoff)
    atomic_json(run_dir / "worker-validation.json", {
        "selection_digest": selection_digest,
        "worker_paths_found": len(worker_paths),
        "workers_present": len(workers),
        "errors": errors,
    })

    summary = {
        "schema_version": 1,
        "approach": APPROACH,
        "accepted": accepted,
        "run_id": args.run_id,
        "run_index": 6,
        "task": "stage6_targeted_hard_survivors",
        "source_sha": args.source_sha,
        "metrics": metrics,
        "worker_error_count": len(errors),
        "scientific_interpretation": (
            "Exact closures are independently verified support-restricted n=6,d=3 "
            "Nullstellensatz certificates. Remaining cases are survivors only relative "
            "to the recorded bounded higher-degree search and are not counterexamples."
        ),
        "next_decision": (
            "Review the compact GPT-5.6 Sol handoff and its smallest exact closures and "
            "survivors before deciding between a new lemma cycle and n=8 transfer."
        ),
    }
    atomic_json(run_dir / "summary.json", summary)
    (run_dir / "README.md").write_text(
        "# Fourth approach Run 006\n\n"
        f"- GitHub Actions run: `{args.run_id}`\n"
        f"- Accepted: `{accepted}`\n"
        f"- GitHub machines: `15`\n"
        f"- Internal workers: `{len(workers)}/60`\n"
        f"- Exact closures: `{len(exact_closures)}`\n"
        f"- Survivors: `{len(survivors)}`\n\n"
        "Survivors are relative to the tested bounded certificate class only.\n",
        encoding="utf-8",
    )
    checksum_lines = []
    for path in sorted(run_dir.iterdir()):
        if path.is_file() and path.name != "checksums.sha256":
            checksum_lines.append(f"{sha256(path)}  {path.name}")
    (run_dir / "checksums.sha256").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    if accepted:
        update_state(repo, summary)
    else:
        control_path = repo / "fourth-approach" / "control.json"
        control = read_json(control_path)
        control.update(
            last_run_id=args.run_id,
            last_run_index=6,
            last_run_accepted=False,
            recommended_next_action="inspect_or_rescue_run_006_without_advancing",
        )
        atomic_json(control_path, control)

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if accepted else 3


if __name__ == "__main__":
    raise SystemExit(main())
