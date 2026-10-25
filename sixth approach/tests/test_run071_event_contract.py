#!/usr/bin/env python3
"""Contract and Boolean semantics tests for run-071 event clauses."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from ortools.sat.python import cp_model


HERE = Path(__file__).resolve().parent
SIXTH = HERE.parent
ROOT = SIXTH.parent
sys.path.insert(0, str(SIXTH))
import run070_contract as contract
import run071_worker as worker


SPEC_PATH = SIXTH / "specs" / "run-071-boundary-event.json"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def target_flag(eta, subset, boundary):
    colour = eta[0]
    return (
        eta == (colour,) * 5
        and subset == tuple(item for item in range(4) if item != colour)
        and boundary == (colour,) * 3
    )


def solve_event(cut, absent=None, escape=None):
    model = cp_model.CpModel()
    active = [model.new_bool_var(f"a{index}") for index in range(contract.ACTIVE_VARIABLES)]
    cache = {}
    worker.add_event_cut(model, active, cut, cache, 0)
    required = set(cut["required_active_variables"])
    for index in range(contract.ACTIVE_VARIABLES):
        value = 1 if index in required else 0
        if absent == index:
            value = 0
        if escape is not None and index in escape:
            value = 1
        model.add(active[index] == value)
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    return solver.status_name(solver.solve(model))


def main():
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    assert spec["schema"] == "run-071-boundary-event-v1"
    assert spec["physical_jobs"] == 18
    assert spec["reserved_runner_slots"] == 2
    assert spec["logical_workers_per_job"] == 4
    assert len(spec["searches"]) == 72
    assert {item["group"] for item in spec["searches"]} == set(range(18))
    assert all(sum(item["group"] == group for item in spec["searches"]) == 4 for group in range(18))
    assert len({item["id"] for item in spec["searches"]}) == 72
    assert spec["source_hashes"] == {
        "run070_contract.py": sha256(SIXTH / "run070_contract.py"),
        "run071_worker.py": sha256(SIXTH / "run071_worker.py"),
        "run071_collect.py": sha256(SIXTH / "run071_collect.py"),
    }
    bundle = worker.load_event_bundle(spec)
    assert bundle["cut_count"] == 2
    for cut in bundle["cuts"]:
        required = set(cut["required_active_variables"])
        alternatives = {tuple(item) for item in cut["escape_alternative_monomials"]}
        row_alternatives = set()
        row_required = set()
        for row in cut["rows"]:
            eta = tuple(row["eta"])
            subset = tuple(row["terminal_subset"])
            boundary = tuple(row["boundary_colours"])
            assert row["target"] == target_flag(eta, subset, boundary)
            all_monomials = set(contract.row_monomials(eta, subset, boundary))
            displayed_required = {tuple(item) for item in row["required_monomials"]}
            displayed_alternatives = {tuple(item) for item in row["alternative_monomials"]}
            assert displayed_required
            assert displayed_required.isdisjoint(displayed_alternatives)
            assert displayed_required | displayed_alternatives == all_monomials
            row_required |= displayed_required
            row_alternatives |= displayed_alternatives
        assert required == {value for monomial in row_required for value in monomial}
        assert alternatives == row_alternatives
        assert solve_event(cut) == "INFEASIBLE"
        assert solve_event(cut, absent=min(required)) in {"OPTIMAL", "FEASIBLE"}
        assert solve_event(cut, escape=set(next(iter(alternatives)))) in {"OPTIMAL", "FEASIBLE"}
    print(json.dumps({"accepted": True, "cuts": len(bundle["cuts"]), "groups": 18}, sort_keys=True))


if __name__ == "__main__":
    main()
