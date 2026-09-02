#!/usr/bin/env python3
"""Search below the Mona Lisa record by exact 2-factors plus geometric patching.

The union of nine strong tours contains very cheap degree-two solutions.  We
solve a sequence of exact minimum 2-factor models, cutting off each collection
of proper subtours.  Every resulting cycle cover is then converted to one
Hamiltonian cycle by repeated exact 2-edge splices.  Candidate splices use both
all parent-union edges and a geometric nearest-neighbour graph.

The patch ranking is vectorized for speed, but every shortlisted move and every
reported final tour is evaluated with exact integer TSPLIB EUC_2D rounding.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set, Tuple

import numpy as np
from ortools.sat.python import cp_model
from scipy.spatial import cKDTree

Edge = Tuple[int, int]


def norm_edge(a: int, b: int) -> Edge:
    if a == b:
        raise ValueError(f"self-loop at {a}")
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


def exact_edge_sum(coords: Sequence[Tuple[int, int]], edges: Iterable[Edge]) -> int:
    return sum(distance(coords, a, b) for a, b in edges)


def exact_tour_length(coords: Sequence[Tuple[int, int]], tour: Sequence[int]) -> int:
    return sum(distance(coords, tour[i], tour[(i + 1) % len(tour)]) for i in range(len(tour)))


def components(n: int, edges: Iterable[Edge]) -> List[List[int]]:
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


def edges_to_adjacency(n: int, edges: Set[Edge]) -> np.ndarray:
    adj = np.zeros((n + 1, 2), dtype=np.int32)
    deg = np.zeros(n + 1, dtype=np.int8)
    for a, b in edges:
        da, db = int(deg[a]), int(deg[b])
        if da >= 2 or db >= 2:
            raise ValueError("factor degree above two")
        adj[a, da] = b
        adj[b, db] = a
        deg[a] += 1
        deg[b] += 1
    bad = np.flatnonzero(deg[1:] != 2)
    if bad.size:
        raise ValueError(f"factor degree check failed, first offset {int(bad[0])}")
    return adj


def adjacency_to_tour(adj: np.ndarray) -> List[int]:
    n = adj.shape[0] - 1
    tour = [1]
    prev, cur = 0, 1
    for _ in range(n - 1):
        x, y = int(adj[cur, 0]), int(adj[cur, 1])
        nxt = x if x != prev else y
        if nxt == 1:
            raise ValueError("premature cycle after patching")
        tour.append(nxt)
        prev, cur = cur, nxt
    if 1 not in (int(adj[cur, 0]), int(adj[cur, 1])):
        raise ValueError("patched path does not close")
    if len(set(tour)) != n:
        raise ValueError("patched tour repeats vertices")
    return tour


def write_tour(path: Path, tour: Sequence[int], length: int, comment: str) -> None:
    with path.open("w", encoding="utf-8") as f:
        f.write("NAME : mona-lisa100K-twofactor-patched\n")
        f.write(f"COMMENT : {comment}; exact TSPLIB length {length}\n")
        f.write("TYPE : TOUR\n")
        f.write(f"DIMENSION : {len(tour)}\nTOUR_SECTION\n")
        f.write("\n".join(map(str, tour)))
        f.write("\n-1\nEOF\n")


def canonical_digest(tour: Sequence[int]) -> str:
    t = list(tour)
    pos = t.index(min(t))
    fwd = t[pos:] + t[:pos]
    rev0 = list(reversed(t))
    pos2 = rev0.index(min(rev0))
    rev = rev0[pos2:] + rev0[:pos2]
    canonical = min(fwd, rev)
    return hashlib.sha256((" ".join(map(str, canonical)) + "\n").encode()).hexdigest()


def build_candidate_pairs(
    coords: Sequence[Tuple[int, int]], union: Set[Edge], nearest: int
) -> Tuple[np.ndarray, np.ndarray]:
    n = len(coords) - 1
    xy = np.asarray(coords[1:], dtype=np.float64)
    tree = cKDTree(xy)
    _dist, idx = tree.query(xy, k=nearest + 1, workers=-1)
    pairs: Set[Edge] = set(union)
    for u0 in range(n):
        u = u0 + 1
        for v0 in np.atleast_1d(idx[u0])[1:]:
            v = int(v0) + 1
            if u != v:
                pairs.add(norm_edge(u, v))
    ordered = sorted(pairs)
    u = np.fromiter((e[0] for e in ordered), dtype=np.int32, count=len(ordered))
    v = np.fromiter((e[1] for e in ordered), dtype=np.int32, count=len(ordered))
    return u, v


def replace_neighbor(adj: np.ndarray, vertex: int, old: int, new: int) -> None:
    if int(adj[vertex, 0]) == old:
        adj[vertex, 0] = new
    elif int(adj[vertex, 1]) == old:
        adj[vertex, 1] = new
    else:
        raise AssertionError(f"{old} is not adjacent to {vertex}")


def vector_rounded_distance(x: np.ndarray, y: np.ndarray, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    dx = x[u] - x[v]
    dy = y[u] - y[v]
    return np.floor(np.sqrt(dx * dx + dy * dy) + 0.5).astype(np.int64)


@dataclass
class PatchResult:
    factor_iteration: int
    factor_length: int
    initial_components: int
    patch_run: int
    random_window: int
    patch_delta: int
    tour_length: int
    exact_moves: List[int]
    digest: str
    output_tour: str


def patch_factor(
    factor_iteration: int,
    factor_edges: Set[Edge],
    factor_length: int,
    comps: List[List[int]],
    coords: Sequence[Tuple[int, int]],
    cand_u: np.ndarray,
    cand_v: np.ndarray,
    run_index: int,
    random_window: int,
    seed: int,
    output: Path,
) -> PatchResult:
    n = len(coords) - 1
    rng = random.Random(seed)
    adj = edges_to_adjacency(n, factor_edges)
    label = np.empty(n + 1, dtype=np.int32)
    members: Dict[int, List[int]] = {}
    for cid, comp in enumerate(comps):
        members[cid] = comp[:]
        label[np.asarray(comp, dtype=np.int32)] = cid

    xi = np.asarray([p[0] for p in coords], dtype=np.int64)
    yi = np.asarray([p[1] for p in coords], dtype=np.int64)
    uv_dist = vector_rounded_distance(xi, yi, cand_u, cand_v)
    deltas_taken: List[int] = []

    while len(members) > 1:
        lu = label[cand_u]
        lv = label[cand_v]
        cross = lu != lv
        indices = np.flatnonzero(cross)
        if not indices.size:
            raise RuntimeError("candidate graph no longer connects distinct cycles")

        u = cand_u[indices]
        v = cand_v[indices]
        base = uv_dist[indices]
        best_delta = np.full(indices.shape[0], np.iinfo(np.int64).max, dtype=np.int64)
        best_choice = np.zeros(indices.shape[0], dtype=np.int8)
        for pu in range(2):
            a = adj[u, pu]
            old_u = vector_rounded_distance(xi, yi, u, a)
            for pv in range(2):
                b = adj[v, pv]
                old_v = vector_rounded_distance(xi, yi, v, b)
                second = vector_rounded_distance(xi, yi, a, b)
                delta = base + second - old_u - old_v
                better = delta < best_delta
                best_delta[better] = delta[better]
                best_choice[better] = 2 * pu + pv

        shortlist_size = min(max(64, random_window * 12), indices.size)
        short_pos = np.argpartition(best_delta, shortlist_size - 1)[:shortlist_size]
        exact_moves: List[Tuple[int, int, int, int, int, int]] = []
        for p in short_pos:
            idx0 = int(indices[int(p)])
            uu, vv = int(cand_u[idx0]), int(cand_v[idx0])
            choice = int(best_choice[int(p)])
            pu, pv = divmod(choice, 2)
            aa, bb = int(adj[uu, pu]), int(adj[vv, pv])
            exact_delta = (
                distance(coords, uu, vv) + distance(coords, aa, bb)
                - distance(coords, uu, aa) - distance(coords, vv, bb)
            )
            exact_moves.append((exact_delta, uu, vv, aa, bb, idx0))
        exact_moves.sort()
        rank_limit = min(random_window, len(exact_moves))
        rank = 0 if random_window <= 1 else rng.randrange(rank_limit)
        delta, u0, v0, a0, b0, _ = exact_moves[rank]

        cu, cv = int(label[u0]), int(label[v0])
        if cu == cv:
            raise AssertionError("stale same-component patch candidate")
        replace_neighbor(adj, u0, a0, v0)
        replace_neighbor(adj, a0, u0, b0)
        replace_neighbor(adj, v0, b0, u0)
        replace_neighbor(adj, b0, v0, a0)

        # Small-to-large relabelling keeps total relabel work near O(n log n).
        if len(members[cu]) < len(members[cv]):
            cu, cv = cv, cu
        moved = members.pop(cv)
        label[np.asarray(moved, dtype=np.int32)] = cu
        members[cu].extend(moved)
        deltas_taken.append(delta)
        print(
            f"patch factor={factor_iteration} run={run_index} cycles={len(members)} "
            f"delta={delta:+d} cumulative={sum(deltas_taken):+d}",
            flush=True,
        )

    tour = adjacency_to_tour(adj)
    exact = exact_tour_length(coords, tour)
    expected = factor_length + sum(deltas_taken)
    if exact != expected:
        raise AssertionError(f"patched exact length {exact} != accounting {expected}")
    name = f"factor{factor_iteration:02d}_run{run_index:02d}_{exact}.tour"
    write_tour(
        output / name,
        tour,
        exact,
        f"factor {factor_iteration}, patch run {run_index}, start {factor_length}",
    )
    return PatchResult(
        factor_iteration=factor_iteration,
        factor_length=factor_length,
        initial_components=len(comps),
        patch_run=run_index,
        random_window=random_window,
        patch_delta=sum(deltas_taken),
        tour_length=exact,
        exact_moves=deltas_taken,
        digest=canonical_digest(tour),
        output_tour=name,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--instance", type=Path, required=True)
    ap.add_argument("--tours", type=Path, nargs="+", required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--seconds", type=float, default=900.0)
    ap.add_argument("--workers", type=int, default=max(1, min(8, os.cpu_count() or 1)))
    ap.add_argument("--nearest", type=int, default=12)
    ap.add_argument("--max-factor-iterations", type=int, default=8)
    ap.add_argument("--random-patches", type=int, default=4)
    ap.add_argument("--seed", type=int, default=260903)
    ap.add_argument("--target", type=int, default=5_757_191)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    deadline = started + args.seconds

    coords = read_tsplib(args.instance)
    n = len(coords) - 1
    tours = [read_tour(path, n) for path in args.tours]
    parent_lengths = [exact_tour_length(coords, t) for t in tours]
    sets = [tour_edges(t) for t in tours]
    fixed = set.intersection(*sets)
    union = set.union(*sets)
    variable = sorted(union - fixed)
    fixed_cost = exact_edge_sum(coords, fixed)

    fixed_deg = np.zeros(n + 1, dtype=np.int8)
    for a, b in fixed:
        fixed_deg[a] += 1
        fixed_deg[b] += 1
    residual = 2 - fixed_deg
    incident: List[List[int]] = [[] for _ in range(n + 1)]
    weights: List[int] = []
    for i, (a, b) in enumerate(variable):
        incident[a].append(i)
        incident[b].append(i)
        weights.append(distance(coords, a, b))

    print("building nearest-neighbour splice graph", flush=True)
    cand_u, cand_v = build_candidate_pairs(coords, union, args.nearest)
    print(
        json.dumps({
            "dimension": n,
            "parent_lengths": parent_lengths,
            "fixed_edges": len(fixed),
            "union_edges": len(union),
            "variable_edges": len(variable),
            "splice_candidate_pairs": int(cand_u.size),
            "nearest": args.nearest,
        }, indent=2),
        flush=True,
    )

    model = cp_model.CpModel()
    x = [model.new_bool_var(f"e{i}") for i in range(len(variable))]
    for v in range(1, n + 1):
        r = int(residual[v])
        if r:
            model.add(sum(x[i] for i in incident[v]) == r)
    model.minimize(fixed_cost + sum(weights[i] * x[i] for i in range(len(variable))))
    base = sets[min(range(len(tours)), key=lambda i: parent_lengths[i])]
    for i, edge in enumerate(variable):
        model.add_hint(x[i], 1 if edge in base else 0)

    cut_signatures: Set[Tuple[int, ...]] = set()
    factors: List[Dict[str, object]] = []
    patches: List[PatchResult] = []
    best_tour_length = min(parent_lengths)
    best_tour_file: str | None = None

    for iteration in range(1, args.max_factor_iterations + 1):
        remaining = deadline - time.monotonic()
        if remaining < 20:
            break
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = remaining
        solver.parameters.num_search_workers = args.workers
        solver.parameters.random_seed = args.seed + iteration
        solver.parameters.cp_model_presolve = True
        solver.parameters.log_search_progress = False
        status_code = solver.solve(model)
        status = solver.status_name(status_code)
        if status_code not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            factors.append({"iteration": iteration, "status": status})
            break

        chosen = {variable[i] for i in range(len(variable)) if solver.boolean_value(x[i])}
        selected = fixed | chosen
        exact = exact_edge_sum(coords, selected)
        objective = int(round(solver.objective_value))
        if exact != objective:
            raise AssertionError(f"factor objective {objective} != exact {exact}")
        comps = components(n, selected)
        comps.sort(key=len, reverse=True)
        factor_path = args.output / f"factor_{iteration:02d}_{exact}_{len(comps)}cycles.edg"
        with factor_path.open("w", encoding="utf-8") as f:
            f.write(f"{n} {len(selected)}\n")
            for a, b in sorted(selected):
                f.write(f"{a} {b} {distance(coords, a, b)}\n")
        info: Dict[str, object] = {
            "iteration": iteration,
            "status": status,
            "length": exact,
            "components": len(comps),
            "largest_component": len(comps[0]),
            "solver_bound": solver.best_objective_bound,
            "factor_file": factor_path.name,
        }
        factors.append(info)
        print(json.dumps(info), flush=True)

        patch_specs = [(0, 1)]
        if len(comps) <= 100:
            patch_specs.extend((j, min(8, 2 + j)) for j in range(1, args.random_patches + 1))
        for run_index, random_window in patch_specs:
            result = patch_factor(
                iteration,
                selected,
                exact,
                comps,
                coords,
                cand_u,
                cand_v,
                run_index,
                random_window,
                args.seed + iteration * 1009 + run_index * 9176,
                args.output,
            )
            patches.append(result)
            if result.tour_length < best_tour_length:
                best_tour_length = result.tour_length
                best_tour_file = result.output_tour
            if result.tour_length < args.target:
                print(f"STRICT IMPROVEMENT FOUND: {result.tour_length}", flush=True)

        if len(comps) == 1:
            break
        comp_id = np.full(n + 1, -1, dtype=np.int32)
        for cid, comp in enumerate(comps):
            comp_id[np.asarray(comp, dtype=np.int32)] = cid
        crossing: List[List[int]] = [[] for _ in comps]
        for i, (a, b) in enumerate(variable):
            ca, cb = int(comp_id[a]), int(comp_id[b])
            if ca != cb:
                crossing[ca].append(i)
                crossing[cb].append(i)
        new_cuts = 0
        for cid in range(1, len(comps)):
            signature = tuple(crossing[cid])
            if signature and signature not in cut_signatures:
                cut_signatures.add(signature)
                model.add(sum(x[i] for i in signature) >= 2)
                new_cuts += 1
        info["new_subtour_cuts"] = new_cuts
        if not new_cuts:
            break

    report = {
        "dimension": n,
        "target_strictly_below": args.target,
        "parent_lengths": parent_lengths,
        "best_parent": min(parent_lengths),
        "best_patched": best_tour_length,
        "improvement": min(parent_lengths) - best_tour_length,
        "best_tour_file": best_tour_file,
        "fixed_edges": len(fixed),
        "union_edges": len(union),
        "splice_candidate_pairs": int(cand_u.size),
        "factor_iterations": factors,
        "patch_results": [asdict(p) for p in patches],
        "elapsed_seconds": time.monotonic() - started,
    }
    (args.output / "twofactor-patch-results.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
