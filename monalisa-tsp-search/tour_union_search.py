#!/usr/bin/env python3
"""Exact recombination search in the union of high-quality Mona Lisa TSP tours.

For a chosen parent set, edges shared by every parent are fixed. The remaining
edge choices form a sparse degree-constrained problem. OR-Tools CP-SAT finds a
minimum-weight 2-factor in that union; violated subtours are cut iteratively
until either a Hamiltonian cycle is obtained or the time limit is reached.

Distances use exact TSPLIB EUC_2D nearest-integer rounding, implemented with
integer arithmetic to avoid floating-point ambiguity.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set, Tuple

from ortools.sat.python import cp_model

Edge = Tuple[int, int]


def norm_edge(a: int, b: int) -> Edge:
    if a == b:
        raise ValueError(f"self-loop at {a}")
    return (a, b) if a < b else (b, a)


def read_tsplib(path: Path) -> List[Tuple[int, int]]:
    dimension = None
    in_coords = False
    raw: Dict[int, Tuple[int, int]] = {}
    with path.open("r", encoding="utf-8", errors="strict") as f:
        for line_no, line in enumerate(f, 1):
            s = line.strip()
            if not s:
                continue
            upper = s.upper()
            if upper.startswith("DIMENSION"):
                dimension = int(s.replace(":", " ").split()[-1])
            elif upper == "NODE_COORD_SECTION":
                in_coords = True
            elif upper == "EOF":
                break
            elif in_coords:
                parts = s.split()
                if len(parts) < 3:
                    raise ValueError(f"bad coordinate line {line_no}: {s!r}")
                i, x, y = map(int, parts[:3])
                raw[i] = (x, y)
    if dimension is None:
        raise ValueError(f"DIMENSION missing in {path}")
    if len(raw) != dimension:
        raise ValueError(f"{path}: expected {dimension} coordinates, got {len(raw)}")
    coords = [(0, 0)] * (dimension + 1)
    for i in range(1, dimension + 1):
        if i not in raw:
            raise ValueError(f"{path}: missing city {i}")
        coords[i] = raw[i]
    return coords


def read_tour(path: Path, n: int) -> List[int]:
    in_tour = False
    tour: List[int] = []
    with path.open("r", encoding="utf-8", errors="strict") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            u = s.upper()
            if u == "TOUR_SECTION":
                in_tour = True
                continue
            if not in_tour:
                continue
            if u == "EOF" or s == "-1":
                break
            for tok in s.split():
                v = int(tok)
                if v == -1:
                    in_tour = False
                    break
                tour.append(v)
            if not in_tour:
                break
    if len(tour) == n + 1 and tour[0] == tour[-1]:
        tour.pop()
    if len(tour) != n:
        raise ValueError(f"{path}: expected {n} cities, got {len(tour)}")
    seen = bytearray(n + 1)
    for v in tour:
        if v < 1 or v > n:
            raise ValueError(f"{path}: city id out of range: {v}")
        if seen[v]:
            raise ValueError(f"{path}: duplicate city: {v}")
        seen[v] = 1
    return tour


def euc_2d(coords: Sequence[Tuple[int, int]], a: int, b: int) -> int:
    xa, ya = coords[a]
    xb, yb = coords[b]
    dx = xa - xb
    dy = ya - yb
    q = dx * dx + dy * dy
    r = math.isqrt(q)
    # sqrt(q) >= r + 1/2 iff 4q >= (2r+1)^2.
    return r + (4 * q >= (2 * r + 1) ** 2)


def tour_edges(tour: Sequence[int]) -> Set[Edge]:
    n = len(tour)
    return {norm_edge(tour[i], tour[(i + 1) % n]) for i in range(n)}


def edge_weight(coords: Sequence[Tuple[int, int]], edge: Edge) -> int:
    return euc_2d(coords, edge[0], edge[1])


def tour_length(coords: Sequence[Tuple[int, int]], tour: Sequence[int]) -> int:
    return sum(euc_2d(coords, tour[i], tour[(i + 1) % len(tour)]) for i in range(len(tour)))


def write_tour(path: Path, tour: Sequence[int], length: int, comment: str) -> None:
    with path.open("w", encoding="utf-8") as f:
        f.write(f"NAME : mona-lisa100K_{length}\n")
        f.write(f"COMMENT : {comment}\n")
        f.write("TYPE : TOUR\n")
        f.write(f"DIMENSION : {len(tour)}\n")
        f.write("TOUR_SECTION\n")
        for v in tour:
            f.write(f"{v}\n")
        f.write("-1\nEOF\n")


def components_from_edges(n: int, edges: Iterable[Edge]) -> List[List[int]]:
    adj: List[List[int]] = [[] for _ in range(n + 1)]
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)
    comps: List[List[int]] = []
    seen = bytearray(n + 1)
    for root in range(1, n + 1):
        if seen[root]:
            continue
        stack = [root]
        seen[root] = 1
        comp: List[int] = []
        while stack:
            v = stack.pop()
            comp.append(v)
            for w in adj[v]:
                if not seen[w]:
                    seen[w] = 1
                    stack.append(w)
        comps.append(comp)
    return comps


def edges_to_tour(n: int, edges: Set[Edge]) -> List[int]:
    if len(edges) != n:
        raise ValueError(f"2-factor should have {n} edges, got {len(edges)}")
    adj: List[List[int]] = [[] for _ in range(n + 1)]
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)
    bad = [v for v in range(1, n + 1) if len(adj[v]) != 2]
    if bad:
        raise ValueError(f"not degree 2; first bad vertices: {bad[:10]}")
    tour = [1]
    prev = 0
    cur = 1
    for _ in range(n - 1):
        x, y = adj[cur]
        nxt = x if x != prev else y
        if nxt == 1:
            raise ValueError("premature subtour")
        tour.append(nxt)
        prev, cur = cur, nxt
    if 1 not in adj[cur]:
        raise ValueError("path does not close")
    if len(set(tour)) != n:
        raise ValueError("tour repeats vertices")
    return tour


@dataclass
class SolveRecord:
    label: str
    parents: List[str]
    parent_lengths: List[int]
    fixed_edges: int
    union_edges: int
    variable_edges: int
    active_vertices: int
    iterations: int
    subtour_cuts: int
    status: str
    best_2factor_value: int | None
    best_cycle: int | None
    elapsed_seconds: float
    output_tour: str | None


def solve_union(
    label: str,
    parent_names: Sequence[str],
    parents: Sequence[Sequence[int]],
    parent_lengths: Sequence[int],
    coords: Sequence[Tuple[int, int]],
    out_dir: Path,
    seconds: float,
    workers: int,
    target: int,
) -> SolveRecord:
    n = len(coords) - 1
    start = time.monotonic()
    edge_sets = [tour_edges(t) for t in parents]
    fixed = set.intersection(*edge_sets)
    union = set.union(*edge_sets)
    variable = sorted(union - fixed)

    fixed_deg = [0] * (n + 1)
    for a, b in fixed:
        fixed_deg[a] += 1
        fixed_deg[b] += 1
    residual = [0] * (n + 1)
    for v in range(1, n + 1):
        residual[v] = 2 - fixed_deg[v]
        if residual[v] < 0:
            raise AssertionError(f"fixed degree >2 at {v}")

    incident: List[List[int]] = [[] for _ in range(n + 1)]
    for i, (a, b) in enumerate(variable):
        incident[a].append(i)
        incident[b].append(i)
    active = sum(1 for v in range(1, n + 1) if residual[v])
    for v in range(1, n + 1):
        if residual[v] and len(incident[v]) < residual[v]:
            raise ValueError(f"insufficient variable degree at {v}")

    weights = [edge_weight(coords, edge) for edge in variable]
    fixed_cost = sum(edge_weight(coords, edge) for edge in fixed)

    print(
        f"[{label}] parents={list(zip(parent_names, parent_lengths))} "
        f"fixed={len(fixed)} union={len(union)} variables={len(variable)} active_vertices={active}",
        flush=True,
    )

    model = cp_model.CpModel()
    x = [model.new_bool_var(f"e{i}") for i in range(len(variable))]
    for v in range(1, n + 1):
        if residual[v]:
            model.add(sum(x[i] for i in incident[v]) == residual[v])
    model.minimize(sum(weights[i] * x[i] for i in range(len(variable))) + fixed_cost)

    base_edges = edge_sets[0]
    for i, edge in enumerate(variable):
        model.add_hint(x[i], 1 if edge in base_edges else 0)

    deadline = start + seconds
    cut_signatures: Set[Tuple[int, ...]] = set()
    iterations = 0
    cuts = 0
    best_2factor_value: int | None = None
    best_cycle: int | None = None
    best_tour: List[int] | None = None
    status = "UNKNOWN"

    while time.monotonic() < deadline:
        iterations += 1
        remaining = max(0.1, deadline - time.monotonic())
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = remaining
        solver.parameters.num_search_workers = workers
        solver.parameters.log_search_progress = False
        solver.parameters.random_seed = 1009 + iterations
        solver.parameters.cp_model_presolve = True
        result = solver.solve(model)
        status = solver.status_name(result)
        if result not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            print(f"[{label}] solver stopped: {status}", flush=True)
            break

        chosen = {variable[i] for i in range(len(variable)) if solver.boolean_value(x[i])}
        selected = fixed | chosen
        objective = int(round(solver.objective_value))
        if best_2factor_value is None or objective < best_2factor_value:
            best_2factor_value = objective

        comps = components_from_edges(n, selected)
        comps.sort(key=len, reverse=True)
        print(
            f"[{label}] iteration={iterations} status={status} value={objective} "
            f"components={len(comps)} largest={len(comps[0])}",
            flush=True,
        )
        if len(comps) == 1:
            candidate = edges_to_tour(n, selected)
            exact = tour_length(coords, candidate)
            if exact != objective:
                raise AssertionError(f"objective {objective} != exact tour length {exact}")
            best_cycle = exact
            best_tour = candidate
            status = "HAMILTONIAN_" + status
            break

        comp_id = [-1] * (n + 1)
        for cid, comp in enumerate(comps):
            for v in comp:
                comp_id[v] = cid
        crossing: List[List[int]] = [[] for _ in comps]
        for i, (a, b) in enumerate(variable):
            ca, cb = comp_id[a], comp_id[b]
            if ca != cb:
                crossing[ca].append(i)
                crossing[cb].append(i)

        new_cuts = 0
        for cid in range(1, len(comps)):
            signature = tuple(crossing[cid])
            if not signature or signature in cut_signatures:
                continue
            cut_signatures.add(signature)
            model.add(sum(x[i] for i in signature) >= 2)
            cuts += 1
            new_cuts += 1
        if new_cuts == 0:
            status = "STALLED_NO_NEW_CUTS"
            break

    output_name: str | None = None
    if best_tour is not None and best_cycle is not None:
        output_name = f"{label}_{best_cycle}.tour"
        write_tour(
            out_dir / output_name,
            best_tour,
            best_cycle,
            f"Exact union recombination of {', '.join(parent_names)}; target < {target}",
        )
        verdict = "IMPROVEMENT" if best_cycle < target else "no improvement"
        print(f"[{label}] cycle={best_cycle}: {verdict}", flush=True)

    return SolveRecord(
        label=label,
        parents=list(parent_names),
        parent_lengths=list(parent_lengths),
        fixed_edges=len(fixed),
        union_edges=len(union),
        variable_edges=len(variable),
        active_vertices=active,
        iterations=iterations,
        subtour_cuts=cuts,
        status=status,
        best_2factor_value=best_2factor_value,
        best_cycle=best_cycle,
        elapsed_seconds=round(time.monotonic() - start, 3),
        output_tour=output_name,
    )


def canonical_name(path: Path) -> str:
    if path.name == "mona-lisa100K.opt.tour":
        return "5757191"
    hits = re.findall(r"\d{7}", path.name)
    return hits[-1] if hits else path.name


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--instance", type=Path, required=True)
    ap.add_argument("--tours", type=Path, nargs="+", required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--pair-seconds", type=float, default=30.0)
    ap.add_argument("--multi-seconds", type=float, default=180.0)
    ap.add_argument("--workers", type=int, default=max(1, min(8, os.cpu_count() or 1)))
    ap.add_argument("--target", type=int, default=5_757_191)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    coords = read_tsplib(args.instance)
    n = len(coords) - 1
    tours: Dict[str, List[int]] = {}
    lengths: Dict[str, int] = {}
    source_paths: Dict[str, str] = {}
    for path in args.tours:
        name = canonical_name(path)
        tour = read_tour(path, n)
        length = tour_length(coords, tour)
        if name in tours:
            raise ValueError(f"duplicate label {name}")
        tours[name] = tour
        lengths[name] = length
        source_paths[name] = str(path)
        print(f"verified {name}: {length} ({path})", flush=True)

    ordered = sorted(tours, key=lambda key: lengths[key])
    if not ordered:
        raise ValueError("no tours")
    base = ordered[0]
    print(f"base={base}, length={lengths[base]}", flush=True)

    records: List[SolveRecord] = []
    for other in ordered[1:]:
        records.append(
            solve_union(
                label=f"pair_{base}_{other}",
                parent_names=[base, other],
                parents=[tours[base], tours[other]],
                parent_lengths=[lengths[base], lengths[other]],
                coords=coords,
                out_dir=args.output,
                seconds=args.pair_seconds,
                workers=args.workers,
                target=args.target,
            )
        )

    seen_sizes: Set[int] = set()
    for size in (3, 4, 5, min(7, len(ordered)), len(ordered)):
        if size > len(ordered) or size < 3 or size in seen_sizes:
            continue
        seen_sizes.add(size)
        names = ordered[:size]
        records.append(
            solve_union(
                label="multi_" + "_".join(names),
                parent_names=names,
                parents=[tours[key] for key in names],
                parent_lengths=[lengths[key] for key in names],
                coords=coords,
                out_dir=args.output,
                seconds=args.multi_seconds,
                workers=args.workers,
                target=args.target,
            )
        )

    best = min((r.best_cycle for r in records if r.best_cycle is not None), default=lengths[base])
    payload = {
        "instance": str(args.instance),
        "dimension": n,
        "target_strictly_below": args.target,
        "input_tours": [
            {"label": key, "length": lengths[key], "path": source_paths[key]} for key in ordered
        ],
        "best_input": lengths[base],
        "best_recombined": best,
        "improvement": lengths[base] - best,
        "records": [asdict(record) for record in records],
    }
    (args.output / "results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Mona Lisa TSP: exact union-recombination search",
        "",
        f"- Dimension: {n}",
        f"- Best verified input tour: {lengths[base]}",
        f"- Best Hamiltonian cycle found in tested unions: {best}",
        f"- Improvement over best input: {lengths[base] - best}",
        "",
        "| model | fixed | union | variables | active vertices | best 2-factor value | cycle | cuts | status | seconds |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|---:|",
    ]
    for record in records:
        lines.append(
            f"| {record.label} | {record.fixed_edges} | {record.union_edges} | "
            f"{record.variable_edges} | {record.active_vertices} | "
            f"{record.best_2factor_value or ''} | {record.best_cycle or ''} | "
            f"{record.subtour_cuts} | {record.status} | {record.elapsed_seconds:.3f} |"
        )
    lines += [
        "",
        "Every reported cycle is reconstructed from its selected edge set and rechecked",
        "with exact integer TSPLIB EUC_2D rounding. A value below 5,757,191 would be",
        "a new record candidate, subject to independent validation.",
    ]
    (args.output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
