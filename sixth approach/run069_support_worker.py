#!/usr/bin/env python3
"""Solve one immutable branch of a neutral cubic support contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

from ortools.sat.python import cp_model


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_dimacs(path: Path):
    variable_count = clause_count = None
    clauses = []
    with path.open("r", encoding="ascii") as stream:
        for raw in stream:
            line = raw.strip()
            if not line or line.startswith("c"):
                continue
            if line.startswith("p "):
                tag, kind, variables, count = line.split()
                if tag != "p" or kind != "cnf" or variable_count is not None:
                    raise ValueError("invalid DIMACS header")
                variable_count = int(variables)
                clause_count = int(count)
                continue
            if variable_count is None:
                raise ValueError("clause before DIMACS header")
            values = [int(value) for value in line.split()]
            if not values or values[-1] != 0 or 0 in values[:-1]:
                raise ValueError("invalid DIMACS clause")
            clause = tuple(values[:-1])
            if not clause or any(abs(literal) > variable_count for literal in clause):
                raise ValueError("invalid DIMACS literal")
            clauses.append(clause)
    if variable_count is None or clause_count != len(clauses):
        raise ValueError("DIMACS count mismatch")
    return variable_count, clauses


def decode_arm(variable: int):
    boundary_colour = variable % 3
    variable //= 3
    terminal = variable % 4
    variable //= 4
    internal_colour = variable % 3
    left = variable // 3
    return left, internal_colour, terminal, boundary_colour


def validate_partition(spec):
    jobs = spec["jobs"]
    if spec["schema"] != "run-069-support-branches-v1" or len(jobs) != 20:
        raise ValueError("unexpected branch specification")
    if len({job["id"] for job in jobs}) != 20:
        raise ValueError("duplicate branch id")
    by_orbit = {}
    for job in jobs:
        by_orbit.setdefault(job["orbit"], []).append(job)
        assumptions = job["assumption_literals"]
        if len(assumptions) != 4:
            raise ValueError("unexpected assumption count")
        if abs(assumptions[-1]) != job["split_arm"] + 1:
            raise ValueError("split literal does not name split arm")
        if (assumptions[-1] > 0) != bool(job["split_value"]):
            raise ValueError("split literal has wrong sign")
    if set(by_orbit) != set(range(10)):
        raise ValueError("target orbit coverage mismatch")
    for orbit, pair in by_orbit.items():
        if len(pair) != 2 or {item["split_value"] for item in pair} != {0, 1}:
            raise ValueError(f"orbit {orbit} is not a binary partition")
        left, right = sorted(pair, key=lambda item: item["split_value"])
        if left["assumption_literals"][:3] != right["assumption_literals"][:3]:
            raise ValueError("paired target assumptions differ")
        if left["split_arm"] != right["split_arm"]:
            raise ValueError("paired split arms differ")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dimacs", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--branches", type=Path, required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--seconds", type=float, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--memory-mib", type=int, default=12000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    branch_spec = json.loads(args.branches.read_text(encoding="utf-8"))
    validate_partition(branch_spec)
    if sha256(args.dimacs) != manifest["dimacs_sha256"]:
        raise ValueError("DIMACS hash differs from manifest")
    if branch_spec["base_dimacs_sha256"] != manifest["dimacs_sha256"]:
        raise ValueError("branch spec names a different DIMACS")
    if manifest["metadata"]["support_region"] != "cross_eq21":
        raise ValueError("manifest is not the C=21 contract")
    branch = next((item for item in branch_spec["jobs"] if item["id"] == args.job_id), None)
    if branch is None:
        raise ValueError("unknown branch id")

    variable_count, clauses = parse_dimacs(args.dimacs)
    if variable_count != manifest["variable_count"] or len(clauses) != manifest["clause_count"]:
        raise ValueError("parsed DIMACS metadata differs from manifest")
    model = cp_model.CpModel()
    variables = [model.new_bool_var(f"v_{index + 1}") for index in range(variable_count)]
    for clause in clauses:
        model.add_bool_or(
            variables[literal - 1]
            if literal > 0
            else variables[-literal - 1].Not()
            for literal in clause
        )
    model.add_assumptions(
        variables[literal - 1]
        if literal > 0
        else variables[-literal - 1].Not()
        for literal in branch["assumption_literals"]
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = args.seconds
    solver.parameters.max_memory_in_mb = args.memory_mib
    solver.parameters.num_workers = args.workers
    solver.parameters.random_seed = 20260811 + 17 * branch["orbit"] + branch["split_value"]
    solver.parameters.linearization_level = 0
    solver.parameters.log_search_progress = False
    started = time.time()
    status = solver.solve(model)
    elapsed = time.time() - started

    result = {
        "schema": "run-069-support-branch-result-v1",
        "evidence_level": "bounded constructive support search",
        "job": branch,
        "status": solver.status_name(status),
        "wall_time_seconds": solver.wall_time,
        "elapsed_seconds": elapsed,
        "workers": args.workers,
        "memory_mib": args.memory_mib,
        "solver": "OR-Tools CP-SAT 9.15.6755",
        "python": platform.python_version(),
        "dimacs_sha256": manifest["dimacs_sha256"],
        "manifest_sha256": sha256(args.manifest),
        "branches_sha256": sha256(args.branches),
        "variable_count": variable_count,
        "clause_count": len(clauses),
        "conflicts": solver.num_conflicts,
        "branches": solver.num_branches,
        "scope_warning": (
            "INFEASIBLE without an independently replayed proof and UNKNOWN are not "
            "mathematical no-go results.  A feasible assignment is only a Boolean "
            "support survivor, not a complex coefficient solution."
        ),
    }
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        assignment = [bool(solver.value(variable)) for variable in variables]
        for clause in clauses:
            if not any(
                assignment[literal - 1] if literal > 0 else not assignment[-literal - 1]
                for literal in clause
            ):
                raise AssertionError("solver assignment fails a source clause")
        for literal in branch["assumption_literals"]:
            if not (assignment[literal - 1] if literal > 0 else not assignment[-literal - 1]):
                raise AssertionError("solver assignment fails a branch assumption")
        selected = [index for index in range(108) if assignment[index]]
        cross = sum(decode_arm(variable)[1] != decode_arm(variable)[3] for variable in selected)
        if cross != 21:
            raise AssertionError("survivor does not have exactly 21 cross-colour arms")
        result.update(
            {
                "assignment_true_literals": [
                    index + 1 for index, value in enumerate(assignment) if value
                ],
                "selected_arms": selected,
                "selected_arm_count": len(selected),
                "cross_colour_selected": cross,
                "selected_arms_sha256": hashlib.sha256(
                    json.dumps(selected, separators=(",", ":")).encode()
                ).hexdigest(),
            }
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"job": args.job_id, "status": result["status"], "survivor": "selected_arms" in result}, sort_keys=True))


if __name__ == "__main__":
    main()
