#!/usr/bin/env python3
"""Exact CP-SAT search for Zhang's 1029-prime Williams-number challenge.

A feasible assignment of this stronger global model is automatically a valid
answer to the original conditional prize problem.  Every emitted candidate is
checked again by direct arbitrary-precision divisibility tests.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import pathlib
import time
import urllib.request
from collections import defaultdict

from ortools.sat.python import cp_model
from sympy import factorint, primitive_root

OFFICIAL_URL = "https://math-zhangzhx.ahnu.edu.cn/SET-1029-PRIMES.txt"
OFFICIAL_SHA256 = "fd7f67051b817842f5795fae812b852efa8007f5478a286365a7236a6a790cd8"
OUT = pathlib.Path(os.environ.get("OUT_DIR", "williams_results"))
OUT.mkdir(parents=True, exist_ok=True)


def get_primes() -> list[int]:
    path = OUT / "SET-1029-PRIMES.txt"
    for attempt in range(8):
        try:
            with urllib.request.urlopen(OFFICIAL_URL, timeout=45) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != OFFICIAL_SHA256:
                raise RuntimeError("official list hash mismatch")
            path.write_bytes(data)
            values = [int(s) for s in data.split()]
            if len(values) != 1029 or len(set(values)) != 1029:
                raise RuntimeError("official list does not contain 1029 distinct integers")
            return values
        except Exception as exc:
            print(f"download attempt {attempt + 1} failed: {exc}", flush=True)
            time.sleep(min(30, 2 ** attempt))
    raise RuntimeError("could not download the official prime list")


def build_cyclic_rows(primes: list[int]):
    facts = [(factorint(p - 1), factorint(p + 1)) for p in primes]
    coordinate_primes = sorted({q for fm, fp in facts for d in (fm, fp) for q in d})
    rows: list[tuple[list[int], int, int, str]] = []

    # Odd cardinality.
    rows.append(([1] * len(primes), 2, 1, "parity"))

    # Units modulo 2^E are C2 x C_(2^(E-2)).  Every official p is 3 mod 4,
    # so odd cardinality supplies the sign; retain the independent 5-log.
    e2 = max(fp.get(2, 0) for _, fp in facts)
    unit_modulus = 2**e2
    order = 2 ** (e2 - 2)
    table = {pow(5, a, unit_modulus): a for a in range(order)}
    coeffs = [table[(-p) % unit_modulus] for p in primes]
    rows.append((coeffs, order, 0, f"2-adic-log-mod-{order}"))

    for q in coordinate_primes:
        if q == 2:
            continue
        exponent = max(max(fm.get(q, 0), fp.get(q, 0)) for fm, fp in facts)
        unit_modulus = q**exponent
        order = (q - 1) * q ** (exponent - 1)
        generator = int(primitive_root(unit_modulus))
        table = {pow(generator, a, unit_modulus): a for a in range(order)}
        coeffs = [table[p % unit_modulus] for p in primes]
        minus = any(fm.get(q, 0) for fm, _ in facts)
        plus = any(fp.get(q, 0) for _, fp in facts)
        if minus == plus:
            raise RuntimeError(f"coordinate q={q} does not have a unique side")
        rhs = 0 if minus else order // 2
        rows.append((coeffs, order, rhs, f"q={q},e={exponent},{'minus' if minus else 'plus'}"))

    if len(rows) != 120:
        raise RuntimeError(f"expected 120 cyclic rows, got {len(rows)}")
    entropy = sum(math.log2(modulus) for _, modulus, _, _ in rows)
    print(f"built {len(rows)} cyclic rows; log2 target group={entropy:.12f}", flush=True)
    return rows


def all_redundant_rows(cyclic_rows):
    """Add exact prime-power projections, including nested levels.

    These rows are logically redundant but expose small modular consequences to
    CP-SAT.  Exact duplicate rows are removed.
    """
    seen: set[tuple[tuple[int, ...], int, int]] = set()
    result: list[tuple[list[int], int, int, str]] = []

    def add(coeffs, modulus, rhs, label):
        c = tuple(int(a) % modulus for a in coeffs)
        b = int(rhs) % modulus
        key = (c, int(modulus), b)
        if key not in seen:
            seen.add(key)
            result.append((list(c), int(modulus), b, label))

    for row_id, (coeffs, modulus, rhs, label) in enumerate(cyclic_rows):
        add(coeffs, modulus, rhs, f"cyclic:{label}")
        for ell, exponent in factorint(modulus).items():
            for level in range(1, exponent + 1):
                d = int(ell**level)
                add(coeffs, d, rhs, f"projection:{label}:mod{d}")
    print(f"using {len(result)} unique exact congruence rows", flush=True)
    return result


def add_congruence(model, x, coeffs, modulus, rhs, name):
    total = sum(coeffs)
    q_lo = (-rhs) // modulus
    q_hi = (total - rhs) // modulus
    q = model.new_int_var(q_lo, q_hi, f"quot_{name}")
    model.add(sum(a * v for a, v in zip(coeffs, x) if a) == rhs + modulus * q)


def solve(primes: list[int], cyclic_rows) -> None:
    card = int(os.environ.get("CARDINALITY", "515"))
    seed = int(os.environ.get("SEED", "20260825"))
    seconds = float(os.environ.get("TIME_LIMIT", "20400"))
    workers = int(os.environ.get("WORKERS", "4"))

    model = cp_model.CpModel()
    x = [model.new_bool_var(f"x_{i}") for i in range(len(primes))]
    model.add(sum(x) == card)

    exact_rows = all_redundant_rows(cyclic_rows)
    for row_id, (coeffs, modulus, rhs, label) in enumerate(exact_rows):
        add_congruence(model, x, coeffs, modulus, rhs, f"r{row_id}")

    # Native XOR constraints expose all first 2-adic conditions explicitly.
    one = model.new_bool_var("fixed_true")
    model.add(one == 1)
    xor_seen: set[tuple[tuple[int, ...], int]] = set()
    xor_count = 0
    for coeffs, _, rhs, label in cyclic_rows:
        ids = tuple(i for i, a in enumerate(coeffs) if a & 1)
        target = rhs & 1
        key = (ids, target)
        if key in xor_seen:
            continue
        xor_seen.add(key)
        literals = [x[i] for i in ids]
        if target == 0:
            literals.append(one)
        model.add_bool_xor(literals)
        xor_count += 1
    print(f"added {xor_count} distinct native XOR rows; cardinality={card}", flush=True)

    solver = cp_model.CpSolver()
    p = solver.parameters
    p.max_time_in_seconds = seconds
    p.num_search_workers = workers
    p.random_seed = seed
    p.randomize_search = True
    p.log_search_progress = True
    p.cp_model_presolve = True
    p.symmetry_level = 2
    p.linearization_level = 2
    p.max_memory_in_mb = 12000
    p.log_to_stdout = True

    started = time.time()
    status = solver.solve(model)
    elapsed = time.time() - started
    status_name = solver.status_name(status)
    summary = {
        "status": status_name,
        "elapsed_seconds": elapsed,
        "cardinality": card,
        "seed": seed,
        "workers": workers,
        "cyclic_rows": len(cyclic_rows),
        "exact_rows_with_redundancy": len(exact_rows),
        "xor_rows": xor_count,
        "conflicts": solver.num_conflicts,
        "branches": solver.num_branches,
        "wall_time": solver.wall_time,
        "response_stats": solver.response_stats(),
    }
    (OUT / "solver_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return

    bits = [int(solver.value(v)) for v in x]
    selected = [p for p, bit in zip(primes, bits) if bit]
    if len(selected) != card or len(selected) % 2 != 1 or len(selected) < 3:
        raise RuntimeError("solver assignment fails cardinality checks")

    # Verify the strong model independently by modular multiplication.
    for coeffs, modulus, rhs, label in cyclic_rows:
        if sum(a * bit for a, bit in zip(coeffs, bits)) % modulus != rhs:
            raise RuntimeError(f"candidate fails cyclic row {label}")

    # Verify the actual prize conditions directly, with no logarithm encoding.
    N = math.prod(selected)
    failures = []
    for p0 in selected:
        if (N - 1) % (p0 - 1) != 0 or (N + 1) % (p0 + 1) != 0:
            failures.append(p0)
    if failures:
        raise RuntimeError(f"direct verification failed for {len(failures)} factors")

    candidate = {
        "selected_indices_zero_based": [i for i, bit in enumerate(bits) if bit],
        "selected_primes": selected,
        "factor_count": len(selected),
        "N_decimal": str(N),
        "direct_verification": "PASS",
    }
    (OUT / "candidate.json").write_text(json.dumps(candidate, indent=2), encoding="utf-8")
    (OUT / "candidate_bits.txt").write_text("\n".join(map(str, bits)) + "\n", encoding="utf-8")
    (OUT / "candidate_primes.txt").write_text("\n".join(map(str, selected)) + "\n", encoding="utf-8")
    print(f"VERIFIED CANDIDATE FOUND: {len(selected)} prime factors", flush=True)


if __name__ == "__main__":
    ps = get_primes()
    rows = build_cyclic_rows(ps)
    solve(ps, rows)
