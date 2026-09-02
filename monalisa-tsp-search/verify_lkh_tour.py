#!/usr/bin/env python3
"""Independently verify an LKH tour for the Mona Lisa TSPLIB instance."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


def read_coords(path: Path) -> list[tuple[int, int]]:
    dimension: int | None = None
    active = False
    data: dict[int, tuple[int, int]] = {}
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
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
            data[i] = (x, y)
    if dimension is None or len(data) != dimension:
        raise ValueError(f"coordinate count mismatch: dimension={dimension}, read={len(data)}")
    return [(0, 0)] + [data[i] for i in range(1, dimension + 1)]


def read_tour(path: Path, n: int) -> list[int]:
    values: list[int] = []
    active = False
    for line in path.read_text(encoding="utf-8").splitlines():
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
            values.append(v)
        if not active:
            break
    if len(values) == n + 1 and values[0] == values[-1]:
        values.pop()
    if len(values) != n:
        raise ValueError(f"expected {n} cities, got {len(values)}")
    seen = bytearray(n + 1)
    for v in values:
        if v < 1 or v > n or seen[v]:
            raise ValueError(f"invalid or duplicate city {v}")
        seen[v] = 1
    return values


def distance(coords: list[tuple[int, int]], a: int, b: int) -> int:
    dx = coords[a][0] - coords[b][0]
    dy = coords[a][1] - coords[b][1]
    q = dx * dx + dy * dy
    r = math.isqrt(q)
    return r + (4 * q >= (2 * r + 1) ** 2)


def cycle_edges(tour: list[int]) -> set[tuple[int, int]]:
    result: set[tuple[int, int]] = set()
    for i, a in enumerate(tour):
        b = tour[(i + 1) % len(tour)]
        result.add((a, b) if a < b else (b, a))
    return result


def canonical_cycle(tour: list[int]) -> list[int]:
    pos = tour.index(min(tour))
    forward = tour[pos:] + tour[:pos]
    rev0 = list(reversed(tour))
    pos2 = rev0.index(min(rev0))
    reverse = rev0[pos2:] + rev0[:pos2]
    return min(forward, reverse)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--instance", type=Path, required=True)
    ap.add_argument("--candidate", type=Path, required=True)
    ap.add_argument("--reference", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--normalized-tour", type=Path)
    ap.add_argument("--target", type=int, default=5_757_191)
    args = ap.parse_args()

    coords = read_coords(args.instance)
    n = len(coords) - 1
    candidate = read_tour(args.candidate, n)
    reference = read_tour(args.reference, n)
    cand_edges = cycle_edges(candidate)
    ref_edges = cycle_edges(reference)
    length = sum(distance(coords, candidate[i], candidate[(i + 1) % n]) for i in range(n))
    ref_length = sum(distance(coords, reference[i], reference[(i + 1) % n]) for i in range(n))
    canonical = canonical_cycle(candidate)
    digest = hashlib.sha256((" ".join(map(str, canonical)) + "\n").encode()).hexdigest()

    report = {
        "dimension": n,
        "verified_candidate_length": length,
        "verified_reference_length": ref_length,
        "improvement": ref_length - length,
        "strict_record_improvement": length < args.target,
        "edges_shared_with_reference": len(cand_edges & ref_edges),
        "edges_removed_from_reference": len(ref_edges - cand_edges),
        "edges_added_to_reference": len(cand_edges - ref_edges),
        "canonical_cycle_sha256": digest,
        "candidate_file": str(args.candidate),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.normalized_tour:
        with args.normalized_tour.open("w", encoding="utf-8") as f:
            f.write("NAME : mona-lisa100K-verified\n")
            f.write(f"COMMENT : Independently verified length {length}\n")
            f.write("TYPE : TOUR\n")
            f.write(f"DIMENSION : {n}\nTOUR_SECTION\n")
            f.write("\n".join(map(str, canonical)))
            f.write("\n-1\nEOF\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
