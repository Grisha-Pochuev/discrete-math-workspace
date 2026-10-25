#!/usr/bin/env python3
"""Deterministic boundary-support contract shared by run-070 tools."""

from __future__ import annotations

import itertools


INTERNAL = tuple(range(5))
TERMINALS = tuple(range(5, 9))
COLOURS = tuple(range(3))
VERTICES = INTERNAL + TERMINALS
EDGES = tuple(itertools.combinations(VERTICES, 2))
EDGE_INDEX = {edge: index for index, edge in enumerate(EDGES)}
ACTIVE_VARIABLES = len(EDGES) * 9
TARGET_KEYS = {
    (tuple([q] * 5), tuple(t for t in range(4) if t != q), tuple([q] * 3))
    for q in COLOURS
}


def perfect_matchings(vertices):
    vertices = tuple(vertices)
    if not vertices:
        yield ()
        return
    first = vertices[0]
    for position in range(1, len(vertices)):
        second = vertices[position]
        rest = vertices[1:position] + vertices[position + 1 :]
        for tail in perfect_matchings(rest):
            yield ((first, second),) + tail


MATCHINGS = {
    subset: tuple(perfect_matchings(INTERNAL + tuple(5 + terminal for terminal in subset)))
    for size in (1, 3)
    for subset in itertools.combinations(range(4), size)
}


def active_index(left, right, left_colour, right_colour):
    if left > right:
        left, right = right, left
        left_colour, right_colour = right_colour, left_colour
    return (EDGE_INDEX[left, right] * 3 + left_colour) * 3 + right_colour


def decode_active(index):
    right_colour = index % 3
    index //= 3
    left_colour = index % 3
    edge = EDGES[index // 3]
    return edge, (left_colour, right_colour)


def row_monomials(eta, terminal_subset, boundary_colours):
    eta = tuple(eta)
    terminal_subset = tuple(terminal_subset)
    boundary_colours = tuple(boundary_colours)
    terminal_map = {
        5 + terminal: colour
        for terminal, colour in zip(terminal_subset, boundary_colours)
    }
    monomials = []
    for matching in MATCHINGS[terminal_subset]:
        variables = []
        for left, right in matching:
            left_colour = eta[left] if left in INTERNAL else terminal_map[left]
            right_colour = eta[right] if right in INTERNAL else terminal_map[right]
            variables.append(active_index(left, right, left_colour, right_colour))
        monomials.append(tuple(sorted(variables)))
    if len(set(monomials)) != len(monomials):
        raise AssertionError("duplicate matching monomial")
    return tuple(monomials)


def target_monomials(colour):
    return row_monomials(
        (colour,) * 5,
        tuple(terminal for terminal in range(4) if terminal != colour),
        (colour,) * 3,
    )


def canonical_target_representatives():
    # Colour zero omits terminal vertex 5 and covers 6,7,8.
    pairings = (
        ((0, 6), (1, 7), (2, 8), (3, 4)),
        ((6, 7), (0, 8), (1, 2), (3, 4)),
        ((6, 8), (0, 7), (1, 2), (3, 4)),
    )
    representatives = []
    for pairing in pairings:
        variables = tuple(
            sorted(active_index(left, right, 0, 0) for left, right in pairing)
        )
        if variables not in target_monomials(0):
            raise AssertionError("bad target representative")
        representatives.append(variables)
    return tuple(representatives)


def iter_row_keys():
    for eta in itertools.product(COLOURS, repeat=5):
        for size in (1, 3):
            for terminal_subset in itertools.combinations(range(4), size):
                for boundary_colours in itertools.product(COLOURS, repeat=size):
                    yield eta, terminal_subset, boundary_colours


def scan_support(active, threat_limit=None):
    active = frozenset(active)
    target_counts = {}
    histogram = {"zero": 0, "unique": 0, "multiple": 0}
    threats = []
    row_count = 0
    for key in iter_row_keys():
        row_count += 1
        present = []
        for monomial in row_monomials(*key):
            if all(variable in active for variable in monomial):
                present.append(monomial)
                if key not in TARGET_KEYS and len(present) >= 2:
                    break
        if key in TARGET_KEYS:
            target_counts[str(key[0][0])] = len(present)
            continue
        if not present:
            histogram["zero"] += 1
        elif len(present) == 1:
            histogram["unique"] += 1
            if threat_limit is None or len(threats) < threat_limit:
                threats.append(
                    {
                        "eta": list(key[0]),
                        "terminal_subset": list(key[1]),
                        "boundary_colours": list(key[2]),
                        "unique_monomial": list(present[0]),
                    }
                )
        else:
            histogram["multiple"] += 1
    if row_count != 243 * 120 or sum(histogram.values()) != row_count - 3:
        raise AssertionError("row coverage mismatch")
    return {
        "row_count": row_count,
        "target_counts": target_counts,
        "forbidden_histogram": histogram,
        "threats": threats,
        "threats_truncated": histogram["unique"] > len(threats),
    }


def validate_support(active):
    replay = scan_support(active, threat_limit=16)
    replay["accepted"] = (
        set(replay["target_counts"]) == {"0", "1", "2"}
        and all(value >= 1 for value in replay["target_counts"].values())
        and replay["forbidden_histogram"]["unique"] == 0
    )
    return replay
