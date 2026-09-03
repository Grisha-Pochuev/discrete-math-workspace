#!/usr/bin/env python3
"""Build and decode the 1,493-vertex contracted Mona Lisa TSP instance.

The graph is derived reproducibly from the nine public historical tours. Edges
shared by all tours form 20 non-trivial paths and isolated vertices. Each
common path is encoded by a degree-two dummy vertex and two compulsory edges;
all remaining edges in the union of the tours are retained directly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set, Tuple

Edge = Tuple[int, int]


def norm_edge(a: int, b: int) -> Edge:
    if a == b:
        raise ValueError(f"self-loop at {a}")
    return (a, b) if a < b else (b, a)


def euc_2d(coords: Sequence[Tuple[int, int]], a: int, b: int) -> int:
    dx = coords[a][0] - coords[b][0]
    dy = coords[a][1] - coords[b][1]
    q = dx * dx + dy * dy
    r = math.isqrt(q)
    return r + (4 * q >= (2 * r + 1) ** 2)


def read_tsplib(path: Path) -> List[Tuple[int, int]]:
    n = None
    active = False
    raw: Dict[int, Tuple[int, int]] = {}
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            s = line.strip()
            if not s:
                continue
            u = s.upper()
            if u.startswith("DIMENSION"):
                n = int(s.replace(":", " ").split()[-1])
            elif u == "NODE_COORD_SECTION":
                active = True
            elif u == "EOF":
                break
            elif active:
                p = s.split()
                if len(p) < 3:
                    raise ValueError(f"bad coordinate line {line_no}: {s!r}")
                i, x, y = map(int, p[:3])
                raw[i - 1] = (x, y)
    if n is None or len(raw) != n:
        raise ValueError(f"coordinate mismatch: n={n}, read={len(raw)}")
    return [raw[i] for i in range(n)]


def read_tsplib_tour(path: Path, n: int) -> List[int]:
    out: List[int] = []
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
                out.append(v - 1)
            if not active:
                break
    if len(out) == n + 1 and out[0] == out[-1]:
        out.pop()
    if len(out) != n or set(out) != set(range(n)):
        raise ValueError(f"invalid tour {path}: {len(out)} entries")
    return out


def read_node_tour(path: Path, n: int) -> List[int]:
    vals = [int(x) for x in path.read_text(encoding="utf-8").split()]
    if vals and vals[0] == n and len(vals) == n + 1:
        vals = vals[1:]
    if len(vals) == n + 1 and vals[0] == vals[-1]:
        vals.pop()
    if len(vals) != n or set(vals) != set(range(n)):
        raise ValueError(f"invalid node tour {path}: {len(vals)} entries")
    return vals


def tour_edges(tour: Sequence[int]) -> Set[Edge]:
    return {norm_edge(tour[i], tour[(i + 1) % len(tour)]) for i in range(len(tour))}


def cycle_from_edges(n: int, edges: Set[Edge], start: int = 0) -> List[int]:
    if len(edges) != n:
        raise ValueError(f"cycle must contain {n} edges, got {len(edges)}")
    adj: List[List[int]] = [[] for _ in range(n)]
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)
    bad = [i for i, row in enumerate(adj) if len(row) != 2]
    if bad:
        raise ValueError(f"degree check failed at {bad[:12]}")
    out = [start]
    prev, cur = -1, start
    for _ in range(n - 1):
        x, y = adj[cur]
        nxt = x if x != prev else y
        if nxt == start:
            raise ValueError("premature cycle")
        out.append(nxt)
        prev, cur = cur, nxt
    if start not in adj[cur] or len(set(out)) != n:
        raise ValueError("cycle does not close through every vertex")
    return out


def write_node_tour(path: Path, tour: Sequence[int]) -> None:
    with path.open("w", encoding="utf-8") as f:
        f.write(f"{len(tour)}\n")
        for i in range(0, len(tour), 10):
            f.write(" ".join(map(str, tour[i:i + 10])) + "\n")


def write_tsplib_tour(path: Path, tour: Sequence[int], length: int) -> None:
    with path.open("w", encoding="utf-8") as f:
        f.write("NAME : mona-lisa100K-contracted-candidate\n")
        f.write(f"COMMENT : exact independently recomputed length {length}\n")
        f.write("TYPE : TOUR\n")
        f.write(f"DIMENSION : {len(tour)}\nTOUR_SECTION\n")
        for v in tour:
            f.write(f"{v + 1}\n")
        f.write("-1\nEOF\n")


def connected_components(n: int, edges: Iterable[Edge]) -> List[List[int]]:
    adj: List[List[int]] = [[] for _ in range(n)]
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)
    seen = bytearray(n)
    comps: List[List[int]] = []
    for root in range(n):
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
    comps.sort(key=min)
    return comps


def path_order(comp: Sequence[int], adj: Sequence[Sequence[int]]) -> List[int]:
    if len(comp) == 1:
        return [comp[0]]
    ends = sorted(v for v in comp if len(adj[v]) == 1)
    if len(ends) != 2:
        raise ValueError(f"fixed component is not a path: size={len(comp)}, ends={len(ends)}")
    out = [ends[0]]
    prev, cur = -1, ends[0]
    while cur != ends[1]:
        nxts = [w for w in adj[cur] if w != prev]
        if len(nxts) != 1:
            raise ValueError("ambiguous fixed-path traversal")
        nxt = nxts[0]
        out.append(nxt)
        prev, cur = cur, nxt
    if len(out) != len(comp):
        raise ValueError("fixed path did not visit its whole component")
    return out


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def cmd_build(args: argparse.Namespace) -> int:
    args.output.mkdir(parents=True, exist_ok=True)
    coords = read_tsplib(args.instance)
    n = len(coords)
    tours = [read_tsplib_tour(p, n) for p in args.tours]
    sets = [tour_edges(t) for t in tours]
    fixed = set.intersection(*sets)
    union = set.union(*sets)
    variable = union - fixed

    fixed_adj: List[List[int]] = [[] for _ in range(n)]
    for a, b in fixed:
        fixed_adj[a].append(b)
        fixed_adj[b].append(a)
    if max(map(len, fixed_adj)) > 2:
        raise ValueError("common-edge graph has degree above two")
    comps = connected_components(n, fixed)

    orig_to_contracted: Dict[int, int] = {}
    fixed_paths: List[Dict[str, object]] = []
    c_edges: Dict[Edge, int] = {}
    edge_mapping: Dict[str, object] = {}
    next_node = 0

    nontrivial = 0
    forced_path_cost = 0
    for comp in comps:
        order = path_order(comp, fixed_adj)
        if len(order) == 1:
            orig_to_contracted[order[0]] = next_node
            next_node += 1
            continue
        nontrivial += 1
        left, right = order[0], order[-1]
        c_left, c_right, dummy = next_node, next_node + 1, next_node + 2
        next_node += 3
        orig_to_contracted[left] = c_left
        orig_to_contracted[right] = c_right
        path_cost = sum(euc_2d(coords, order[i], order[i + 1]) for i in range(len(order) - 1))
        forced_path_cost += path_cost
        e1, e2 = norm_edge(c_left, dummy), norm_edge(c_right, dummy)
        c_edges[e1] = path_cost
        c_edges[e2] = 0
        edge_mapping[f"{e1[0]},{e1[1]}"] = {"kind": "forced", "path_index": len(fixed_paths)}
        edge_mapping[f"{e2[0]},{e2[1]}"] = {"kind": "forced", "path_index": len(fixed_paths)}
        fixed_paths.append({
            "component_min": min(comp),
            "left": left,
            "right": right,
            "nodes": order,
            "cost": path_cost,
            "contracted": [c_left, c_right, dummy],
        })

    for a, b in sorted(variable):
        if a not in orig_to_contracted or b not in orig_to_contracted:
            raise ValueError(f"non-fixed edge touches an internal fixed-path vertex: {(a, b)}")
        ca, cb = orig_to_contracted[a], orig_to_contracted[b]
        ce = norm_edge(ca, cb)
        w = euc_2d(coords, a, b)
        if ce in c_edges:
            raise ValueError(f"contracted parallel edge at {ce}")
        c_edges[ce] = w
        edge_mapping[f"{ce[0]},{ce[1]}"] = {"kind": "direct", "original": [a, b]}

    c_n = next_node
    graph_path = args.output / "contracted.edg"
    with graph_path.open("w", encoding="utf-8") as f:
        f.write(f"{c_n} {len(c_edges)}\n")
        for (a, b), w in sorted(c_edges.items()):
            f.write(f"{a} {b} {w}\n")

    lengths = [sum(euc_2d(coords, tour[j], tour[(j + 1) % n]) for j in range(n)) for tour in tours]
    best_idx = min(range(len(tours)), key=lambda i: lengths[i])
    best_edges = sets[best_idx]
    c_tour_edges: Set[Edge] = set()
    for ce_key, meta in edge_mapping.items():
        ca, cb = map(int, ce_key.split(","))
        if meta["kind"] == "forced":
            c_tour_edges.add((ca, cb))
        else:
            oe = norm_edge(*meta["original"])
            if oe in best_edges:
                c_tour_edges.add((ca, cb))
    c_tour = cycle_from_edges(c_n, c_tour_edges, 0)
    initial_path = args.output / "initial.node_tour"
    write_node_tour(initial_path, c_tour)
    initial_length = sum(c_edges[norm_edge(c_tour[i], c_tour[(i + 1) % c_n])] for i in range(c_n))

    mapping = {
        "original_n": n,
        "contracted_n": c_n,
        "full_original_edges": len(union),
        "fixed_original_edges": len(fixed),
        "contracted_edges": len(c_edges),
        "fixed_path_components": nontrivial,
        "forced_path_cost": forced_path_cost,
        "initial_length": initial_length,
        "best_tour_index": best_idx,
        "orig_to_contracted": {str(k): v for k, v in orig_to_contracted.items()},
        "edge_mapping": edge_mapping,
        "fixed_paths": fixed_paths,
        "fixed_edges": [list(e) for e in sorted(fixed)],
    }
    mapping_path = args.output / "mapping.json"
    mapping_path.write_text(json.dumps(mapping, separators=(",", ":")), encoding="utf-8")
    report = {
        "original_n": n,
        "contracted_n": c_n,
        "union_edges": len(union),
        "fixed_edges": len(fixed),
        "variable_edges": len(variable),
        "contracted_edges": len(c_edges),
        "fixed_components": len(comps),
        "nontrivial_fixed_paths": nontrivial,
        "isolated_fixed_components": len(comps) - nontrivial,
        "forced_path_cost": forced_path_cost,
        "initial_length": initial_length,
        "input_lengths": lengths,
        "graph_sha256": sha256(graph_path),
        "tour_sha256": sha256(initial_path),
        "mapping_sha256": sha256(mapping_path),
    }
    expected = {
        "original_n": 100000,
        "contracted_n": 1493,
        "union_edges": 107962,
        "fixed_edges": 98547,
        "variable_edges": 9415,
        "contracted_edges": 9455,
        "fixed_components": 1453,
        "nontrivial_fixed_paths": 20,
        "isolated_fixed_components": 1433,
        "forced_path_cost": 5685396,
        "initial_length": 5757191,
    }
    for key, val in expected.items():
        if report[key] != val:
            raise AssertionError(f"{key}: got {report[key]}, expected {val}")
    (args.output / "build-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


def cmd_decode(args: argparse.Namespace) -> int:
    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
    coords = read_tsplib(args.instance)
    c_n = int(mapping["contracted_n"])
    c_tour = read_node_tour(args.candidate, c_n)
    selected = {norm_edge(c_tour[i], c_tour[(i + 1) % c_n]) for i in range(c_n)}
    original_edges: Set[Edge] = {tuple(e) for e in mapping["fixed_edges"]}
    direct_count = 0
    forced_count = 0
    for ce in selected:
        meta = mapping["edge_mapping"].get(f"{ce[0]},{ce[1]}")
        if meta is None:
            raise ValueError(f"candidate uses edge absent from mapping: {ce}")
        if meta["kind"] == "direct":
            original_edges.add(norm_edge(*meta["original"]))
            direct_count += 1
        else:
            forced_count += 1
    original_tour = cycle_from_edges(len(coords), original_edges, 0)
    length = sum(euc_2d(coords, original_tour[i], original_tour[(i + 1) % len(original_tour)]) for i in range(len(original_tour)))
    args.output.mkdir(parents=True, exist_ok=True)
    out_tour = args.output / f"decoded_{length}.tour"
    write_tsplib_tour(out_tour, original_tour, length)
    report = {
        "contracted_vertices": c_n,
        "contracted_edges_selected": len(selected),
        "direct_edges_selected": direct_count,
        "forced_edges_selected": forced_count,
        "original_edges_reconstructed": len(original_edges),
        "exact_length": length,
        "strict_improvement": length < args.target,
        "candidate_sha256": sha256(args.candidate),
        "decoded_tour_sha256": sha256(out_tour),
        "decoded_tour": str(out_tour),
    }
    (args.output / "decode-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    b.add_argument("--instance", type=Path, required=True)
    b.add_argument("--tours", type=Path, nargs="+", required=True)
    b.add_argument("--output", type=Path, required=True)
    b.set_defaults(func=cmd_build)
    d = sub.add_parser("decode")
    d.add_argument("--instance", type=Path, required=True)
    d.add_argument("--mapping", type=Path, required=True)
    d.add_argument("--candidate", type=Path, required=True)
    d.add_argument("--output", type=Path, required=True)
    d.add_argument("--target", type=int, default=5757191)
    d.set_defaults(func=cmd_decode)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
