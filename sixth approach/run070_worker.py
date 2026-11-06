#!/usr/bin/env python3
"""Run one single-threaded lazy support search from an immutable specification."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

from ortools.sat.python import cp_model

import run070_contract as contract


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def add_monomial(model, active, monomial, cache, prefix):
    key = tuple(monomial)
    variable = cache.get(key)
    if variable is None:
        variable = model.new_bool_var(f"{prefix}_{len(cache)}")
        for index in key:
            model.add_implication(variable, active[index])
        cache[key] = variable
    return variable


def add_unique_cut(model, active, threat, monomial_cache, cut_index):
    key = (
        tuple(threat["eta"]),
        tuple(threat["terminal_subset"]),
        tuple(threat["boundary_colours"]),
    )
    unique = tuple(threat["unique_monomial"])
    alternatives = [m for m in contract.row_monomials(*key) if m != unique]
    literals = [active[index].Not() for index in unique]
    literals.extend(
        add_monomial(model, active, monomial, monomial_cache, f"c{cut_index}")
        for monomial in alternatives
    )
    model.add_bool_or(literals)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--search-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    if spec["schema"] != "run-070-boundary-support-v1":
        raise ValueError("wrong spec schema")
    search = next((item for item in spec["searches"] if item["id"] == args.search_id), None)
    if search is None:
        raise ValueError("unknown search id")
    if len(spec["searches"]) != 80 or spec["logical_workers_per_job"] != 4:
        raise ValueError("wrong search coverage")

    model = cp_model.CpModel()
    active = [model.new_bool_var(f"a_{index}") for index in range(contract.ACTIVE_VARIABLES)]
    monomial_cache = {}
    representative = contract.canonical_target_representatives()[search["target_orbit"]]
    for index in representative:
        model.add(active[index] == 1)
    for colour in (1, 2):
        row = [
            add_monomial(model, active, monomial, monomial_cache, f"target{colour}")
            for monomial in contract.target_monomials(colour)
        ]
        model.add_bool_or(row)

    tie_weights = [1 + ((index * 1103515245 + search["seed"]) % 7) for index in range(len(active))]
    model.minimize(
        10000 * sum(active[index] for index in range(len(active)))
        + sum(tie_weights[index] * active[index] for index in range(len(active)))
    )

    started = time.monotonic()
    rounds = 0
    cuts = 0
    last_replay = None
    last_support = None
    status_name = "TIME_LIMIT"
    solver_stats = {}
    while rounds < spec["max_rounds"]:
        remaining = spec["seconds_per_search"] - (time.monotonic() - started)
        if remaining <= 2:
            break
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = min(spec["seconds_per_round"], remaining)
        solver.parameters.max_memory_in_mb = spec["memory_mib_per_search"]
        solver.parameters.num_workers = 1
        solver.parameters.random_seed = search["seed"] + rounds * 1009
        solver.parameters.randomize_search = True
        solver.parameters.linearization_level = 0
        solver.parameters.log_search_progress = False
        status = solver.solve(model)
        rounds += 1
        solver_stats = {
            "cp_status": solver.status_name(status),
            "conflicts": solver.num_conflicts,
            "branches": solver.num_branches,
            "wall_time_seconds": solver.wall_time,
        }
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            status_name = "MODEL_INFEASIBLE" if status == cp_model.INFEASIBLE else "TIME_LIMIT"
            break
        support = [index for index, variable in enumerate(active) if solver.value(variable)]
        replay = contract.scan_support(support, threat_limit=spec["cuts_per_round"])
        last_replay = replay
        last_support = support
        if any(value < 1 for value in replay["target_counts"].values()):
            raise AssertionError("solver support misses a required row")
        if replay["forbidden_histogram"]["unique"] == 0:
            status_name = "SURVIVOR"
            break
        for threat in replay["threats"]:
            add_unique_cut(model, active, threat, monomial_cache, cuts)
            cuts += 1

    result = {
        "schema": "run-070-boundary-support-result-v1",
        "evidence_level": "bounded constructive support search",
        "search": search,
        "status": status_name,
        "rounds": rounds,
        "cuts": cuts,
        "elapsed_seconds": time.monotonic() - started,
        "workers": 1,
        "memory_mib": spec["memory_mib_per_search"],
        "solver": "OR-Tools CP-SAT 9.15.6755",
        "python": platform.python_version(),
        "spec_sha256": sha256(args.spec),
        "contract_sha256": sha256(Path(__file__).with_name("run070_contract.py")),
        "solver_stats": solver_stats,
        "scope_warning": "A survivor is a necessary cancellation support, not a coefficient solution; negative bounded statuses are not no-go theorems.",
    }
    if last_replay is not None:
        result["last_replay"] = {
            key: value for key, value in last_replay.items() if key != "threats"
        }
    if status_name == "SURVIVOR":
        final = contract.validate_support(last_support)
        if not final["accepted"]:
            raise AssertionError("survivor failed exact replay")
        result.update(
            {
                "selected_active": last_support,
                "selected_count": len(last_support),
                "selected_sha256": hashlib.sha256(
                    json.dumps(last_support, separators=(",", ":")).encode()
                ).hexdigest(),
                "exact_replay": final,
            }
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"id": args.search_id, "status": status_name, "rounds": rounds, "cuts": cuts}, sort_keys=True))


if __name__ == "__main__":
    main()
