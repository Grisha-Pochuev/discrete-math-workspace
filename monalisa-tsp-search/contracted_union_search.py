#!/usr/bin/env python3
"""Exact Hamiltonian search in the union of historical Mona Lisa tours.

All edges shared by every input tour are compulsory within the restricted
union problem.  They form vertex-disjoint paths.  We contract each such path
to one component and use CP-SAT's global Circuit constraint on the contracted
graph.  Extra constraints retain the two endpoint ports of every fixed path,
so every solution expands to exactly one Hamiltonian cycle of the original
100,000-city instance.

The arithmetic is integral throughout.  TSPLIB EUC_2D weights are evaluated
with integer square roots and exact nearest-integer rounding.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set, Tuple

from ortools.sat.python import cp_model

Edge = Tuple[int, int]


def norm_edge(a: int, b: int) -> Edge:
    if a == b:
        raise ValueError(f"self-loop at city {a}")
    return (a, b) if a < b else (b, a)


def read_tsplib(path: Path) -> List[Tuple[int, int]]:
    dimension: int | None = None
    active = False
    raw: Dict[int, Tuple[int, int]] = {}
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            s = line.strip()
            if not s:
                continue
            u = s.upper()
            if u.startswith("DIMENSION"):
                dimension = int(s.replace(":", " ").split()[-1])
            elif u == "NODE_COORD_SECTION":
                active = True
            elif u == "EOF":
                break
            elif active:
                p = s.split()
                if len(p) < 3:
                    raise ValueError(f"bad coordinate line {line_no}: {s!r}")
                i, x, y = map(int, p[:3])
                raw[i] = (x, y)
    if dimension is None or len(raw) != dimension:
        raise ValueError(f"coordinate mismatch: dimension={dimension}, read={len(raw)}")
    return [(0, 0)] + [raw[i] for i in range(1, dimension + 1)]


def read_tour(path: Path, n: int) -> List[int]:
    tour: List[int] = []
    active = False
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            if s.upper() == "TOUR_SECTION":
                active = True
                continue
            if not active:
                continue
            for token in s.split():
                v = int(token)
                if v == -1:
                    active = False
                    break
                tour.append(v)
            if not active:
                break
    if len(tour) == n + 1 and tour[0] == tour[-1]:
        tour.pop()
    if len(tour) != n:
        raise ValueError(f"{path}: expected {n} cities, got {len(tour)}")
    seen = bytearray(n + 1)
    for v in tour:
        if v < 1 or v > n or seen[v]:
            raise ValueError(f"{path}: invalid or repeated city {v}")
        seen[v] = 1
    return tour


def distance(coords: Sequence[Tuple[int, int]], a: int, b: int) -> int:
    dx = coords[a][0] - coords[b][0]
    dy = coords[a][1] - coords[b][1]
    q = dx * dx + dy * dy
    r = math.isqrt(q)
    return r + (4 * q >= (2 * r + 1) ** 2)


def tour_edges(tour: Sequence[int]) -> Set[Edge]:
    return {norm_edge(tour[i], tour[(i + 1) % len(tour)]) for i in range(len(tour))}


def tour_length(coords: Sequence[Tuple[int, int]], tour: Sequence[int]) -> int:
    return sum(distance(coords, tour[i], tour[(i + 1) % len(tour)]) for i in range(len(tour)))


class DSU:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n + 1))
        self.size = [1] * (n + 1)

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> bool:
        a, b = self.find(a), self.find(b)
        if a == b:
            return False
        if self.size[a] < self.size[b]:
            a, b = b, a
        self.parent[b] = a
        self.size[a] += self.size[b]
        return True


def components_from_edges(n: int, edges: Iterable[Edge]) -> List[List[int]]:
    adj: List[List[int]] = [[] for _ in range(n + 1)]
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)
    seen = bytearray(n + 1)
    out: List[List[int]] = []
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
        out.append(comp)
    return out


def edges_to_tour(n: int, edges: Set[Edge]) -> List[int]:
    if len(edges) != n:
        raise ValueError(f"Hamiltonian cycle needs {n} edges, got {len(edges)}")
    adj: List[List[int]] = [[] for _ in range(n + 1)]
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)
    bad = [v for v in range(1, n + 1) if len(adj[v]) != 2]
    if bad:
        raise ValueError(f"degree check failed at {bad[:10]}")
    tour = [1]
    prev, cur = 0, 1
    for _ in range(n - 1):
        x, y = adj[cur]
        nxt = x if x != prev else y
        if nxt == 1:
            raise ValueError("premature cycle")
        tour.append(nxt)
        prev, cur = cur, nxt
    if 1 not in adj[cur] or len(set(tour)) != n:
        raise ValueError("cycle verification failed")
    return tour


def write_tour(path: Path, tour: Sequence[int], length: int) -> None:
    with path.open("w", encoding="utf-8") as f:
        f.write("NAME : mona-lisa100K-contracted-union\n")
        f.write(f"COMMENT : Independently checked exact length {length}\n")
        f.write("TYPE : TOUR\n")
        f.write(f"DIMENSION : {len(tour)}\n")
        f.write("TOUR_SECTION\n")
        f.write("\n".join(map(str, tour)))
        f.write("\n-1\nEOF\n")


def canonical_digest(tour: Sequence[int]) -> str:
    pos = tour.index(min(tour))
    fwd = list(tour[pos:]) + list(tour[:pos])
    rev0 = list(reversed(tour))
    pos2 = rev0.index(min(rev0))
    rev = rev0[pos2:] + rev0[:pos2]
    canonical = min(fwd, rev)
    return hashlib.sha256((" ".join(map(str, canonical)) + "\n").encode()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--instance", type=Path, required=True)
    ap.add_argument("--tours", type=Path, nargs="+", required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--seconds", type=float, default=1200.0)
    ap.add_argument("--workers", type=int, default=max(1, min(8, os.cpu_count() or 1)))
    ap.add_argument("--upper-bound", type=int, default=5_757_190,
                    help="search only for cycles at or below this exact length")
    ap.add_argument("--seed", type=int, default=260903)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    coords = read_tsplib(args.instance)
    n = len(coords) - 1
    tours = [read_tour(path, n) for path in args.tours]
    lengths = [tour_length(coords, tour) for tour in tours]
    edge_sets = [tour_edges(tour) for tour in tours]
    fixed = set.intersection(*edge_sets)
    union = set.union(*edge_sets)

    fixed_deg = [0] * (n + 1)
    fixed_adj: List[List[int]] = [[] for _ in range(n + 1)]
    dsu = DSU(n)
    for a, b in fixed:
        fixed_deg[a] += 1
        fixed_deg[b] += 1
        if fixed_deg[a] > 2 or fixed_deg[b] > 2:
            raise AssertionError("common edges cannot have degree above two")
        fixed_adj[a].append(b)
        fixed_adj[b].append(a)
        if not dsu.union(a, b):
            raise ValueError("the compulsory common-edge graph contains a cycle")

    roots = sorted({dsu.find(v) for v in range(1, n + 1)})
    root_to_comp = {root: i for i, root in enumerate(roots)}
    comp_of = [-1] * (n + 1)
    comp_vertices: List[List[int]] = [[] for _ in roots]
    for v in range(1, n + 1):
        c = root_to_comp[dsu.find(v)]
        comp_of[v] = c
        comp_vertices[c].append(v)

    # Every nontrivial fixed component must be a path; each singleton has one
    # port of residual degree two, while a path has two distinct degree-one ports.
    residual = [2 - fixed_deg[v] for v in range(n + 1)]
    component_ports: List[List[Tuple[int, int]]] = []
    for cid, vertices in enumerate(comp_vertices):
        ports = [(v, residual[v]) for v in vertices if residual[v] > 0]
        total = sum(r for _, r in ports)
        if total != 2:
            raise ValueError(f"fixed component {cid} has residual degree {total}, not 2")
        if len(vertices) > 1 and (len(ports) != 2 or any(r != 1 for _, r in ports)):
            raise ValueError(f"fixed component {cid} is not a path: ports={ports}")
        component_ports.append(ports)

    variable_all = sorted(union - fixed)
    variable: List[Edge] = []
    ignored_internal: List[Edge] = []
    for edge in variable_all:
        if comp_of[edge[0]] == comp_of[edge[1]]:
            ignored_internal.append(edge)
        else:
            variable.append(edge)

    print(json.dumps({
        "dimension": n,
        "input_lengths": lengths,
        "fixed_edges": len(fixed),
        "union_edges": len(union),
        "raw_variable_edges": len(variable_all),
        "cross_component_variable_edges": len(variable),
        "ignored_internal_closing_edges": len(ignored_internal),
        "contracted_components": len(comp_vertices),
        "nontrivial_fixed_paths": sum(len(vs) > 1 for vs in comp_vertices),
        "isolated_fixed_vertices": sum(len(vs) == 1 for vs in comp_vertices),
        "upper_bound": args.upper_bound,
    }, indent=2), flush=True)

    incident: List[List[int]] = [[] for _ in range(n + 1)]
    weights: List[int] = []
    for i, (a, b) in enumerate(variable):
        incident[a].append(i)
        incident[b].append(i)
        weights.append(distance(coords, a, b))
    for v in range(1, n + 1):
        if residual[v] > len(incident[v]):
            raise ValueError(f"city {v} needs {residual[v]} variable edges but has {len(incident[v])}")

    fixed_cost = sum(distance(coords, a, b) for a, b in fixed)
    model = cp_model.CpModel()
    forward: List[cp_model.IntVar] = []
    reverse: List[cp_model.IntVar] = []
    arcs: List[Tuple[int, int, cp_model.IntVar]] = []
    for i, (a, b) in enumerate(variable):
        ca, cb = comp_of[a], comp_of[b]
        uv = model.new_bool_var(f"e{i}_c{ca}_to_c{cb}")
        vu = model.new_bool_var(f"e{i}_c{cb}_to_c{ca}")
        forward.append(uv)
        reverse.append(vu)
        model.add(uv + vu <= 1)
        arcs.append((ca, cb, uv))
        arcs.append((cb, ca, vu))
    model.add_circuit(arcs)

    # Preserve the endpoint/port structure of every contracted fixed path.
    for v in range(1, n + 1):
        if residual[v]:
            model.add(sum(forward[i] + reverse[i] for i in incident[v]) == residual[v])

    variable_cost = sum(weights[i] * (forward[i] + reverse[i]) for i in range(len(variable)))
    model.add(variable_cost + fixed_cost <= args.upper_bound)
    model.minimize(variable_cost + fixed_cost)

    # Give the solver a near-feasible orientation based on the best input tour.
    best_index = min(range(len(tours)), key=lambda i: lengths[i])
    base = tours[best_index]
    directed_base: Dict[Edge, Tuple[int, int]] = {}
    for i, a in enumerate(base):
        b = base[(i + 1) % n]
        directed_base[norm_edge(a, b)] = (a, b)
    for i, (a, b) in enumerate(variable):
        direction = directed_base.get((a, b))
        if direction == (a, b):
            model.add_hint(forward[i], 1)
            model.add_hint(reverse[i], 0)
        elif direction == (b, a):
            model.add_hint(forward[i], 0)
            model.add_hint(reverse[i], 1)
        else:
            model.add_hint(forward[i], 0)
            model.add_hint(reverse[i], 0)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = args.seconds
    solver.parameters.num_search_workers = args.workers
    solver.parameters.random_seed = args.seed
    solver.parameters.log_search_progress = True
    solver.parameters.cp_model_presolve = True
    result = solver.solve(model)
    status = solver.status_name(result)
    report: Dict[str, object] = {
        "dimension": n,
        "input_tours": [str(p) for p in args.tours],
        "input_lengths": lengths,
        "best_input_length": min(lengths),
        "upper_bound_tested": args.upper_bound,
        "fixed_edges": len(fixed),
        "union_edges": len(union),
        "variable_edges": len(variable),
        "ignored_internal_edges": len(ignored_internal),
        "contracted_components": len(comp_vertices),
        "fixed_cost": fixed_cost,
        "status": status,
        "wall_time_seconds": solver.wall_time,
        "elapsed_seconds": time.monotonic() - started,
        "best_objective_bound": None,
        "candidate_length": None,
        "strict_record_improvement": False,
        "canonical_cycle_sha256": None,
    }
    try:
        report["best_objective_bound"] = solver.best_objective_bound
    except Exception:
        pass

    if result in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        selected = set(fixed)
        selected_variable = 0
        for i, edge in enumerate(variable):
            if solver.boolean_value(forward[i]) or solver.boolean_value(reverse[i]):
                selected.add(edge)
                selected_variable += 1
        components = components_from_edges(n, selected)
        if len(components) != 1:
            raise AssertionError(f"Circuit model expanded to {len(components)} components")
        tour = edges_to_tour(n, selected)
        exact = tour_length(coords, tour)
        objective = int(round(solver.objective_value))
        if exact != objective:
            raise AssertionError(f"solver objective {objective} differs from exact {exact}")
        if exact > args.upper_bound:
            raise AssertionError(f"candidate {exact} violates bound {args.upper_bound}")
        output_tour = args.output / f"candidate_{exact}.tour"
        write_tour(output_tour, tour, exact)
        report.update({
            "candidate_length": exact,
            "selected_variable_edges": selected_variable,
            "strict_record_improvement": exact < min(lengths),
            "canonical_cycle_sha256": canonical_digest(tour),
            "output_tour": str(output_tour),
        })

    (args.output / "contracted-union-result.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
