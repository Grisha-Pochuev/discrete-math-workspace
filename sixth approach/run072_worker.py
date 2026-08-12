#!/usr/bin/env python3
"""Run one independent single-threaded finite-event search."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import platform
from pathlib import Path
import sys
import time

try:
    from ortools.sat.python import cp_model
except ModuleNotFoundError:
    runtime = Path(__file__).resolve().parents[2] / ".local-tools" / "ortools-runtime2"
    sys.path.insert(0, str(runtime))
    from ortools.sat.python import cp_model

import run072_contract as contract


def atomic_gzip(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as stream:
            stream.write(contract.canonical_bytes(payload))
    temporary.replace(path)


def atomic_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    temporary.replace(path)


def add_monomial(model, active, monomial, cache, prefix):
    key = tuple(monomial)
    if not key:
        return model.new_constant(1)
    variable = cache.get(key)
    if variable is None:
        variable = model.new_bool_var(f"{prefix}_{len(cache)}")
        for index in key:
            model.add_implication(variable, active[index])
        cache[key] = variable
    return variable


def add_clause(model, active, clause, cache, prefix):
    literals = [active[index].Not() for index in clause["required"]]
    literals.extend(
        add_monomial(model, active, monomial, cache, prefix)
        for monomial in clause["alternatives"]
    )
    if not literals:
        raise ValueError("empty finite-event clause")
    model.add_bool_or(literals)


def validate_spec(spec, spec_path):
    if (
        spec.get("schema") != "run-072-finite-events-v1"
        or spec.get("run_id") != "run-072"
        or spec.get("physical_jobs") != 20
        or spec.get("reserved_runner_slots") != 0
        or spec.get("logical_workers_per_job") != 4
        or len(spec.get("searches", [])) != 80
        or any(
            sum(item["group"] == group for item in spec["searches"]) != 4
            for group in range(20)
        )
    ):
        raise ValueError("wrong immutable spec")
    source_root = Path(__file__).resolve().parent
    for name, digest in spec["source_hashes"].items():
        if contract.sha256_file(source_root / name) != digest:
            raise ValueError(f"source identity mismatch: {name}")


def write_checkpoint(path, spec_sha, input_sha, search, additions, status, rounds):
    payload = {
        "schema": "run-072-finite-events-checkpoint-v1",
        "spec_sha256": spec_sha,
        "input_sha256": input_sha,
        "search": search,
        "added_clauses": additions,
        "added_clause_count": len(additions),
        "last_status": status,
        "rounds": rounds,
    }
    payload["canonical_outcome_sha256"] = hashlib.sha256(
        contract.canonical_bytes(payload)
    ).hexdigest()
    atomic_gzip(path, payload)
    return contract.sha256_file(path), payload["canonical_outcome_sha256"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--search-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    validate_spec(spec, args.spec)
    search = next((item for item in spec["searches"] if item["id"] == args.search_id), None)
    if search is None:
        raise ValueError("unknown search id")
    compact = contract.load_compact_input(
        spec["input_path"], spec["input_sha256"], spec["input_outcome_sha256"]
    )
    candidates = contract.candidate_entries()
    forbidden_rows, target_rows = contract.build_rows(candidates)
    rows = forbidden_rows + target_rows

    model = cp_model.CpModel()
    active = [model.new_bool_var(f"a_{index}") for index in range(len(candidates))]
    cache = {}
    base_clauses = compact["source_clauses"] + compact["learned_clauses"]
    known_keys = set()
    for index, clause in enumerate(base_clauses):
        add_clause(model, active, clause, cache, f"b{index}")
        known_keys.add(contract.clause_key(clause["required"], clause["alternatives"]))

    seed = search["seed"]
    tie = [1 + ((index * 1103515245 + seed) % 7) for index in range(len(active))]
    model.minimize(
        10000 * sum(active)
        + sum(tie[index] * active[index] for index in range(len(active)))
    )

    max_seconds = min(2.0, spec["seconds_per_search"]) if args.smoke else spec["seconds_per_search"]
    max_rounds = min(1, spec["max_rounds"]) if args.smoke else spec["max_rounds"]
    cuts_per_round = min(8, spec["cuts_per_round"]) if args.smoke else spec["cuts_per_round"]
    started = time.monotonic()
    rounds = 0
    additions = []
    status = "TIME_LIMIT"
    last_solver = {}
    solver_status_histogram = {}
    last_histogram = {}
    last_threat_count = None
    last_support = 0
    checkpoint_sha = checkpoint_outcome = None
    while rounds < max_rounds:
        remaining = max_seconds - (time.monotonic() - started)
        if remaining <= 0.25:
            break
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = min(spec["seconds_per_round"], remaining)
        solver.parameters.max_memory_in_mb = spec["memory_mib_per_search"]
        solver.parameters.num_workers = 1
        solver.parameters.random_seed = seed + rounds * 1009
        solver.parameters.randomize_search = True
        solver.parameters.linearization_level = 0
        solve_status = solver.solve(model)
        rounds += 1
        last_solver = {
            "status": solver.status_name(solve_status),
            "conflicts": solver.num_conflicts,
            "branches": solver.num_branches,
            "wall_time_seconds": solver.wall_time,
        }
        solver_name = solver.status_name(solve_status)
        solver_status_histogram[solver_name] = solver_status_histogram.get(solver_name, 0) + 1
        if solve_status == cp_model.INFEASIBLE:
            status = "MODEL_INFEASIBLE"
        elif solve_status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            # A round-level UNKNOWN is diagnostic, not a reason to abandon the
            # remaining five-hour budget.  Retry with the next deterministic
            # seed until the global deadline or round cap.
            status = "RUNNING"
        else:
            last_support = sum(
                1 << index for index, variable in enumerate(active) if solver.value(variable)
            )
            threats, last_threat_count, last_histogram = contract.scan_support(
                last_support, rows, len(candidates), cuts_per_round
            )
            if not threats:
                if last_threat_count != 0 or not contract.constraints_hold(last_support, rows):
                    raise AssertionError("truncated scan hid a violation")
                status = "SURVIVOR"
            else:
                for threat in threats:
                    key = contract.clause_key(threat["required"], threat["alternatives"])
                    if key in known_keys:
                        continue
                    contract.validate_dynamic_clause(threat, rows, len(candidates))
                    known_keys.add(key)
                    add_clause(model, active, threat, cache, f"d{len(additions)}")
                    additions.append(threat)
                status = "RUNNING"
        checkpoint_sha, checkpoint_outcome = write_checkpoint(
            args.checkpoint, contract.sha256_file(args.spec), spec["input_sha256"],
            search, additions, status, rounds,
        )
        if status in {"SURVIVOR", "MODEL_INFEASIBLE", "TIME_LIMIT"}:
            break

    if status == "RUNNING":
        status = "TIME_LIMIT"
    checkpoint_sha, checkpoint_outcome = write_checkpoint(
        args.checkpoint, contract.sha256_file(args.spec), spec["input_sha256"],
        search, additions, status, rounds,
    )
    result = {
        "schema": "run-072-finite-events-result-v1",
        "evidence_level": "bounded independent native search with exact survivor replay",
        "search": search,
        "status": status,
        "rounds": rounds,
        "elapsed_seconds": time.monotonic() - started,
        "workers": 1,
        "memory_mib": spec["memory_mib_per_search"],
        "base_clause_count": compact["total_clause_count"],
        "added_clause_count": len(additions),
        "total_clause_count": compact["total_clause_count"] + len(additions),
        "last_solver": last_solver,
        "solver_status_histogram": dict(sorted(solver_status_histogram.items())),
        "last_row_histogram": last_histogram,
        "last_threat_count": last_threat_count,
        "last_selected_candidate_count": last_support.bit_count() if last_support else None,
        "spec_sha256": contract.sha256_file(args.spec),
        "input_sha256": spec["input_sha256"],
        "input_outcome_sha256": spec["input_outcome_sha256"],
        "contract_sha256": contract.sha256_file(Path(__file__).with_name("run072_contract.py")),
        "worker_sha256": contract.sha256_file(__file__),
        "checkpoint_file": args.checkpoint.name,
        "checkpoint_sha256": checkpoint_sha,
        "checkpoint_outcome_sha256": checkpoint_outcome,
        "solver": "OR-Tools CP-SAT 9.15.6755",
        "python": platform.python_version(),
        "scope_warning": "Only an exactly replayed survivor is scientific data; bounded negative status is diagnostic.",
    }
    if status == "SURVIVOR":
        survivor = contract.exact_survivor_payload(
            last_support, candidates, forbidden_rows, target_rows
        )
        survivor_path = args.output.with_name("survivor.json")
        atomic_json(survivor_path, survivor)
        result.update({
            "survivor_file": survivor_path.name,
            "survivor_sha256": contract.sha256_file(survivor_path),
            "survivor_outcome_sha256": survivor["canonical_outcome_sha256"],
            "selected_candidate_count": survivor["selected_count"],
        })
    result["canonical_outcome_sha256"] = hashlib.sha256(
        contract.canonical_bytes(result)
    ).hexdigest()
    atomic_json(args.output, result)
    print(json.dumps({
        "id": search["id"], "status": status, "rounds": rounds,
        "added_clauses": len(additions),
        "selected_candidate_count": result.get("selected_candidate_count"),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
