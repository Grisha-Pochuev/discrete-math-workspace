#!/usr/bin/env python3
"""Exact CP-SAT searches for Zhang's 1029-prime Williams-number challenge.

The target here is Zhang's stronger sufficient system: the selected-prime
product is 1 modulo every p-1 master component and -1 modulo every p+1
master component.  Any returned solution is independently checked against
the original per-selected-prime divisibilities before being written.
"""
from __future__ import annotations

import argparse
import json
import gzip
import math
import os
import random
import sys
import time
from pathlib import Path
from typing import Iterable, Sequence

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parent


def load_json(name: str):
    path = ROOT / name
    if path.exists():
        with path.open() as f:
            return json.load(f)
    gz = ROOT / (name + ".gz")
    with gzip.open(gz, "rt") as f:
        return json.load(f)


def load_primes() -> list[int]:
    return [int(s) for s in (ROOT / "SET-1029-PRIMES.txt").read_text().split()]


def independent_xor_rows(rows: Sequence[dict], n: int) -> list[tuple[int, list[int]]]:
    """Return a row-equivalent independent GF(2) system (rhs, support)."""
    basis: dict[int, tuple[int, int]] = {}
    for row in rows:
        bits = 0
        for i, a in enumerate(row["a"]):
            if a & 1:
                bits ^= 1 << i
        rhs = int(row["b"]) & 1
        while bits:
            p = bits.bit_length() - 1
            if p not in basis:
                basis[p] = (bits, rhs)
                break
            bbits, brhs = basis[p]
            bits ^= bbits
            rhs ^= brhs
        if not bits and rhs:
            raise RuntimeError("inconsistent XOR subsystem")
    out = []
    for p in sorted(basis, reverse=True):
        bits, rhs = basis[p]
        support = []
        while bits:
            low = bits & -bits
            support.append(low.bit_length() - 1)
            bits ^= low
        out.append((rhs, support))
    return out


def add_xor(model: cp_model.CpModel, x: Sequence[cp_model.IntVar], rhs: int,
            support: Sequence[int], one: cp_model.IntVar) -> None:
    lits = [x[i] for i in support]
    # AddBoolXOr enforces odd parity.  Appending a fixed true literal flips it.
    if rhs == 0:
        lits.append(one)
    if not lits:
        if rhs:
            model.add(0 == 1)
        return
    model.add_bool_xor(lits)


def add_mod_row(model: cp_model.CpModel, x: Sequence[cp_model.IntVar], row: dict,
                prefix: str) -> cp_model.IntVar | None:
    m = int(row.get("m", row.get("order")))
    b = int(row["b"]) % m
    coeff = []
    for value in row["a"]:
        a = int(value) % m
        if a > m // 2:
            a -= m
        coeff.append(a)
    terms = [(a, x[i]) for i, a in enumerate(coeff) if a]
    if not terms:
        if b:
            model.add(0 == 1)
        return None
    min_sum = sum(min(0, a) for a, _ in terms)
    max_sum = sum(max(0, a) for a, _ in terms)
    k_lo = math.ceil((min_sum - b) / m)
    k_hi = math.floor((max_sum - b) / m)
    if k_lo > k_hi:
        model.add(0 == 1)
        return None
    k = model.new_int_var(k_lo, k_hi, f"{prefix}_q")
    expr = cp_model.LinearExpr.weighted_sum(
        [v for _, v in terms], [a for a, _ in terms]
    )
    model.add(expr == b + m * k)
    return k


def add_cardinality(model: cp_model.CpModel, x: Sequence[cp_model.IntVar], weight: int) -> None:
    if weight >= 0:
        model.add(sum(x) == weight)
    else:
        k = model.new_int_var(0, len(x) // 2, "odd_cardinality_half")
        model.add(sum(x) == 2 * k + 1)


def build_model(mode: str, weight: int, active_split_primes: set[int] | None = None,
                hint: Sequence[int] | None = None) -> tuple[cp_model.CpModel, list[cp_model.IntVar], dict]:
    global_rows = load_json("global_rows.json")
    split_rows = load_json("split_rows.json")
    n = len(global_rows[0]["a"])
    model = cp_model.CpModel()
    x = [model.new_bool_var(f"x_{i}") for i in range(n)]
    one = model.new_bool_var("const_true")
    model.add(one == 1)
    add_cardinality(model, x, weight)

    meta = {"mode": mode, "weight": weight, "n": n}

    if mode in {"global", "hybrid"}:
        for j, row in enumerate(global_rows):
            add_mod_row(model, x, row, f"g{j}")
        meta["global_rows"] = len(global_rows)

    if mode in {"split", "hybrid", "incremental"}:
        selected = split_rows
        if active_split_primes is not None:
            selected = [r for r in split_rows if int(r["p"]) in active_split_primes]
        xor_source = [r for r in selected if int(r["p"]) == 2 and int(r["e"]) == 1]
        xor_rows = independent_xor_rows(xor_source, n)
        for rhs, support in xor_rows:
            add_xor(model, x, rhs, support, one)
        nonbinary = [r for r in selected if not (int(r["p"]) == 2 and int(r["e"]) == 1)]
        for j, row in enumerate(nonbinary):
            add_mod_row(model, x, row, f"s{j}")
        meta.update({
            "active_split_primes": sorted(active_split_primes) if active_split_primes else None,
            "split_rows": len(selected),
            "xor_rank": len(xor_rows),
            "nonbinary_rows": len(nonbinary),
        })

    if hint is not None:
        if len(hint) != n:
            raise ValueError("bad hint length")
        for v, val in zip(x, hint):
            model.add_hint(v, int(val))
        model.add_hint(one, 1)
        meta["hint_weight"] = sum(hint)

    return model, x, meta


def safe_set(params, name: str, value) -> bool:
    try:
        setattr(params, name, value)
        return True
    except Exception:
        return False


def solve_once(model: cp_model.CpModel, x: Sequence[cp_model.IntVar], seed: int,
               seconds: float, workers: int, flavour: str) -> tuple[int, cp_model.CpSolver, list[int] | None]:
    solver = cp_model.CpSolver()
    p = solver.parameters
    p.max_time_in_seconds = float(seconds)
    p.num_search_workers = int(workers)
    p.random_seed = int(seed)
    p.log_search_progress = True
    safe_set(p, "randomize_search", True)
    safe_set(p, "permute_variable_randomly", True)
    safe_set(p, "permute_presolve_constraint_order", True)
    safe_set(p, "use_absl_random", True)
    # Diversify the portfolio without relying on unstable enum names.
    if flavour == "jump":
        safe_set(p, "use_feasibility_jump", True)
    elif flavour == "lns":
        safe_set(p, "use_lns_only", True)
    elif flavour == "no_presolve":
        safe_set(p, "cp_model_presolve", False)
    elif flavour == "fixed":
        safe_set(p, "fix_variables_to_their_hinted_value", False)
    print("PARAMETERS", p, flush=True)
    t0 = time.time()
    status = solver.solve(model)
    elapsed = time.time() - t0
    print("STATUS", solver.status_name(status), "elapsed", elapsed, flush=True)
    print(solver.response_stats(), flush=True)
    vals = None
    if status in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        vals = [int(solver.value(v)) for v in x]
        print("FOUND_WEIGHT", sum(vals), flush=True)
    return status, solver, vals



def solver_value(solver, snake: str, camel: str):
    """Read an OR-Tools solver statistic across API naming variants."""
    attr = getattr(solver, snake, None)
    if attr is None:
        attr = getattr(solver, camel)
    return attr() if callable(attr) else attr


def verify_candidate(vals: Sequence[int], primes: Sequence[int], global_rows: Sequence[dict]) -> dict:
    selected = [p for p, bit in zip(primes, vals) if bit]
    N = math.prod(selected)
    direct_minus_bad = [p for p in selected if (N - 1) % (p - 1)]
    direct_plus_bad = [p for p in selected if (N + 1) % (p + 1)]
    global_bad = []
    for row in global_rows:
        m = int(row["m"])
        lhs = sum(int(a) * int(v) for a, v in zip(row["a"], vals)) % m
        if lhs != int(row["b"]) % m:
            global_bad.append({"name": row["name"], "lhs": lhs, "rhs": int(row["b"]) % m, "m": m})
    return {
        "weight": len(selected),
        "N_bits": N.bit_length(),
        "N_digits": len(str(N)),
        "selected": selected,
        "N": str(N),
        "direct_minus_bad": direct_minus_bad,
        "direct_plus_bad": direct_plus_bad,
        "global_bad": global_bad,
        "verified": not direct_minus_bad and not direct_plus_bad and not global_bad and len(selected) >= 3 and len(selected) % 2 == 1,
    }


def choose_hint(seed: int, weight: int) -> tuple[str, list[int]]:
    hints = load_json("hints.json")
    candidates = hints
    if weight >= 0:
        exact = [h for h in hints if sum(h["x"]) == weight]
        if exact:
            candidates = exact
        else:
            best_d = min(abs(sum(h["x"]) - weight) for h in hints)
            candidates = [h for h in hints if abs(sum(h["x"]) - weight) == best_d]
    h = candidates[seed % len(candidates)]
    return h["name"], [int(v) for v in h["x"]]


def write_result(tag: str, payload: dict) -> None:
    out = ROOT / "out"
    out.mkdir(exist_ok=True)
    (out / f"{tag}.json").write_text(json.dumps(payload, indent=2))
    if payload.get("verification", {}).get("verified"):
        v = payload["verification"]
        lines = [
            "VERIFIED WILLIAMS NUMBER FROM ZHANG'S 1029 PRIMES",
            f"number_of_prime_factors={v['weight']}",
            f"N_bits={v['N_bits']}",
            f"N_digits={v['N_digits']}",
            "prime_factors:",
            *[str(p) for p in v["selected"]],
            "N:",
            v["N"],
        ]
        (out / f"{tag}_CERTIFICATE.txt").write_text("\n".join(lines) + "\n")


def incremental(args, hint_name: str, hint: list[int]) -> dict:
    split_rows = load_json("split_rows.json")
    bases = sorted({int(r["p"]) for r in split_rows})
    # Stages chosen by cumulative information, with denser early checkpoints.
    stage_sets: list[set[int]] = []
    active: set[int] = set()
    cumulative = 0.0
    next_cut = 240.0
    by_base = {}
    for p in bases:
        by_base[p] = sum(math.log2(int(r["m"])) for r in split_rows if int(r["p"]) == p)
    for p in bases:
        active.add(p)
        cumulative += by_base[p]
        if cumulative + 1e-9 >= next_cut or p == bases[-1]:
            stage_sets.append(set(active))
            if next_cut < 500:
                next_cut += 120
            elif next_cut < 800:
                next_cut += 100
            else:
                next_cut += 70
    if stage_sets[-1] != set(bases):
        stage_sets.append(set(bases))

    current_hint = hint
    stages = []
    remaining = float(args.seconds)
    for stage_idx, aset in enumerate(stage_sets):
        left = len(stage_sets) - stage_idx
        # Give early stages enough to repair, reserve at least half for final.
        if left == 1:
            budget = remaining
        else:
            budget = min(max(35.0, args.seconds * 0.08), remaining / (left + 0.7))
        model, x, meta = build_model("incremental", args.weight, aset, current_hint)
        print("INCREMENTAL_STAGE", stage_idx, "bases", sorted(aset), "budget", budget, "meta", meta, flush=True)
        status, solver, vals = solve_once(model, x, args.seed + 1009 * stage_idx, budget,
                                          args.workers, args.flavour)
        remaining -= budget
        rec = {
            "stage": stage_idx,
            "active_bases": sorted(aset),
            "budget": budget,
            "status": solver.status_name(status),
            "wall_time": solver_value(solver, "wall_time", "WallTime"),
            "branches": solver_value(solver, "num_branches", "NumBranches"),
            "conflicts": solver_value(solver, "num_conflicts", "NumConflicts"),
        }
        if vals is not None:
            rec["weight"] = sum(vals)
            current_hint = vals
        stages.append(rec)
        if vals is None:
            return {"stages": stages, "values": None, "final_status": solver.status_name(status)}
    return {"stages": stages, "values": current_hint, "final_status": stages[-1]["status"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["global", "split", "hybrid", "incremental"], required=True)
    ap.add_argument("--weight", type=int, default=-1, help="exact weight, or -1 for merely odd")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--seconds", type=float, default=2700.0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--flavour", choices=["default", "jump", "lns", "no_presolve", "fixed"], default="default")
    args = ap.parse_args()

    primes = load_primes()
    global_rows = load_json("global_rows.json")
    hint_name, hint = choose_hint(args.seed, args.weight)
    print("RUN", vars(args), "hint", hint_name, "hint_weight", sum(hint), flush=True)
    tag = f"{args.mode}_w{args.weight}_s{args.seed}_{args.flavour}"
    payload = {"args": vars(args), "hint": hint_name, "hint_weight": sum(hint), "tag": tag}

    if args.mode == "incremental":
        inc = incremental(args, hint_name, hint)
        payload["incremental"] = {k: v for k, v in inc.items() if k != "values"}
        vals = inc["values"]
        if vals is not None:
            payload["verification"] = verify_candidate(vals, primes, global_rows)
        write_result(tag, payload)
        return 0 if payload.get("verification", {}).get("verified") else 2

    model, x, meta = build_model(args.mode, args.weight, hint=hint)
    payload["model"] = meta
    status, solver, vals = solve_once(model, x, args.seed, args.seconds, args.workers, args.flavour)
    payload["status"] = solver.status_name(status)
    payload["solver"] = {
        "wall_time": solver_value(solver, "wall_time", "WallTime"),
        "branches": solver_value(solver, "num_branches", "NumBranches"),
        "conflicts": solver_value(solver, "num_conflicts", "NumConflicts"),
        "response_stats": solver.response_stats(),
    }
    if vals is not None:
        payload["verification"] = verify_candidate(vals, primes, global_rows)
    write_result(tag, payload)
    return 0 if payload.get("verification", {}).get("verified") else 2


if __name__ == "__main__":
    raise SystemExit(main())
