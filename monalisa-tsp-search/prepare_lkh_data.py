#!/usr/bin/env python3
"""Convert the published ElimTSP Mona Lisa edge set to an LKH candidate file.

The ElimTSP file is in Concorde edge format (0-based endpoints).  LKH candidate
files are 1-based, list every node, and contain endpoint/alpha pairs.  We use
alpha=0 so no published edge is deprioritized.  The best known tour edges are
also inserted defensively and their coverage is reported.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
from typing import Iterable, TextIO


def open_text(path: Path) -> TextIO:
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("r", encoding="utf-8")


def read_edge_file(path: Path) -> tuple[int, list[tuple[int, int, int]]]:
    with open_text(path) as f:
        header = f.readline().split()
        if len(header) < 2:
            raise ValueError(f"bad Concorde edge header in {path}: {header}")
        n, expected = map(int, header[:2])
        edges: list[tuple[int, int, int]] = []
        seen: set[tuple[int, int]] = set()
        for line_no, line in enumerate(f, 2):
            p = line.split()
            if not p:
                continue
            if len(p) < 3:
                raise ValueError(f"bad edge line {line_no}: {line!r}")
            a, b, w = map(int, p[:3])
            if not (0 <= a < n and 0 <= b < n) or a == b:
                raise ValueError(f"invalid endpoints on line {line_no}: {(a, b)}")
            e = (a, b) if a < b else (b, a)
            if e in seen:
                raise ValueError(f"duplicate edge {e} on line {line_no}")
            seen.add(e)
            edges.append((e[0], e[1], w))
    if len(edges) != expected:
        raise ValueError(f"expected {expected} edges, read {len(edges)}")
    return n, edges


def read_tour(path: Path, n: int) -> list[int]:
    tour: list[int] = []
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
    if len(tour) != n or set(tour) != set(range(1, n + 1)):
        raise ValueError(f"invalid tour {path}: {len(tour)} entries")
    return tour


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--edges", type=Path, required=True)
    ap.add_argument("--tour", type=Path, required=True)
    ap.add_argument("--candidate", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()

    n, edges = read_edge_file(args.edges)
    tour = read_tour(args.tour, n)
    adjacency: list[set[int]] = [set() for _ in range(n)]
    weights: dict[tuple[int, int], int] = {}
    for a, b, w in edges:
        adjacency[a].add(b)
        adjacency[b].add(a)
        weights[(a, b)] = w

    missing: list[tuple[int, int]] = []
    for i, a1 in enumerate(tour):
        b1 = tour[(i + 1) % n]
        a, b = a1 - 1, b1 - 1
        e = (a, b) if a < b else (b, a)
        if e not in weights:
            missing.append(e)
            adjacency[e[0]].add(e[1])
            adjacency[e[1]].add(e[0])

    args.candidate.parent.mkdir(parents=True, exist_ok=True)
    with args.candidate.open("w", encoding="utf-8") as f:
        f.write(f"{n}\n")
        for a in range(n):
            neighbors = sorted(adjacency[a])
            fields = [str(a + 1), "0", str(len(neighbors))]
            for b in neighbors:
                fields.extend((str(b + 1), "0"))
            f.write(" ".join(fields) + "\n")
        f.write("-1\n")

    degrees = [len(v) for v in adjacency]
    report = {
        "dimension": n,
        "published_edges": len(edges),
        "candidate_undirected_edges": sum(degrees) // 2,
        "tour_edges_missing_from_published_graph": len(missing),
        "missing_tour_edges_zero_based": missing,
        "minimum_degree": min(degrees),
        "maximum_degree": max(degrees),
        "average_degree": sum(degrees) / n,
        "isolated_vertices": sum(d == 0 for d in degrees),
        "degree_below_two": sum(d < 2 for d in degrees),
    }
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
