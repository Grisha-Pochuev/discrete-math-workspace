#!/usr/bin/env python3
"""Build either immutable formula in the neutral run-084 pair."""

from __future__ import annotations

from collections import Counter
import argparse
import hashlib
import itertools
import json
from pathlib import Path


ROWS = tuple(range(5))
TERMINALS = tuple(range(8))
DISTANT = (5, 6, 7)
COLOURS = tuple(range(3))
WORDS = tuple(itertools.product(COLOURS, repeat=4))
PERMUTATIONS = {
    root: tuple(itertools.permutations(row for row in ROWS if row != root))
    for root in ROWS
}


def entry_id(row: int, terminal: int, colour: int) -> int:
    return (row * 8 + terminal) * 3 + colour


VALID_BITS = tuple(
    entry_id(row, terminal, colour)
    for row in ROWS
    for terminal in TERMINALS
    if row != terminal
    for colour in COLOURS
)


def expected(pattern: str, root: int, word) -> bool:
    if len(set(word)) != 1:
        return False
    colour = word[0]
    if pattern == "111":
        return root < 3 and colour == root
    return (root == 0 and colour in (0, 1)) or (root == 1 and colour == 2)


def matching_bits(root: int, word, permutation):
    terminals = (root, *DISTANT)
    return tuple(sorted(
        entry_id(permutation[position], terminals[position], word[position])
        for position in range(4)
    ))


MATCHING_BITS = {
    (root, word_index, permutation_index): matching_bits(root, word, permutation)
    for root in ROWS
    for word_index, word in enumerate(WORDS)
    for permutation_index, permutation in enumerate(PERMUTATIONS[root])
}


def circuit_key(first_bits, second_bits):
    first = frozenset(first_bits)
    second = frozenset(second_bits)
    forward = (tuple(sorted(first - second)), tuple(sorted(second - first)))
    reverse = (forward[1], forward[0])
    return min(forward, reverse)


def cycle_type(first, second):
    right_position = {row: position for position, row in enumerate(second)}
    relative = tuple(right_position[row] for row in first)
    seen = set()
    lengths = []
    for start in range(4):
        if start in seen:
            continue
        current = start
        length = 0
        while current not in seen:
            seen.add(current)
            length += 1
            current = relative[current]
        if length > 1:
            lengths.append(length)
    return tuple(sorted(lengths, reverse=True))


class Formula:
    def __init__(self):
        self.variable_count = 0
        self.clauses = []
        self.family_counts = Counter()

    def variable(self) -> int:
        self.variable_count += 1
        return self.variable_count

    def add(self, literals, family: str):
        clause = tuple(int(value) for value in literals)
        if not clause or any(value == 0 for value in clause):
            raise AssertionError("invalid CNF clause")
        self.clauses.append(clause)
        self.family_counts[family] += 1

    def at_most(self, literals, bound: int, prefix: str):
        values = tuple(literals)
        count = len(values)
        if bound < 0:
            raise AssertionError("negative cardinality bound")
        if bound >= count:
            return
        if bound == 0:
            for value in values:
                self.add((-value,), prefix)
            return
        state = {
            (index, rank): self.variable()
            for index in range(1, count)
            for rank in range(1, bound + 1)
        }
        self.add((-values[0], state[1, 1]), prefix)
        for rank in range(2, bound + 1):
            self.add((-state[1, rank],), prefix)
        for index in range(2, count):
            value = values[index - 1]
            self.add((-value, state[index, 1]), prefix)
            self.add((-state[index - 1, 1], state[index, 1]), prefix)
            for rank in range(2, bound + 1):
                self.add(
                    (-value, -state[index - 1, rank - 1], state[index, rank]),
                    prefix,
                )
                self.add(
                    (-state[index - 1, rank], state[index, rank]), prefix
                )
            self.add((-value, -state[index - 1, bound]), prefix)
        self.add((-values[-1], -state[count - 1, bound]), prefix)


def orthogonality_group(pattern: str, row: int, terminal: int):
    bits = []
    for colour in COLOURS:
        if pattern == "111":
            excluded = terminal < 3 and colour == terminal
        else:
            excluded = (
                (terminal == 0 and colour in (0, 1))
                or (terminal == 1 and colour == 2)
            )
        if not excluded:
            bits.append(entry_id(row, terminal, colour))
    return tuple(bits)


def build(pattern: str):
    if pattern not in ("111", "21"):
        raise ValueError("pattern must be 111 or 21")
    formula = Formula()

    support_vars = {bit: formula.variable() for bit in VALID_BITS}
    if len(support_vars) != 105:
        raise AssertionError("valid support variable count mismatch")

    matching_vars = {}
    for key, bits in MATCHING_BITS.items():
        variable = formula.variable()
        matching_vars[key] = variable
        entries = tuple(support_vars[bit] for bit in bits)
        for entry in entries:
            formula.add((-variable, entry), "matching_equivalence")
        formula.add((variable, *(-entry for entry in entries)), "matching_equivalence")

    rows = {}
    for root in ROWS:
        for word_index, word in enumerate(WORDS):
            rows[root, word_index] = tuple(
                matching_vars[root, word_index, permutation_index]
                for permutation_index in range(24)
            )
            if expected(pattern, root, word):
                formula.add(rows[root, word_index], "required_nonempty")
            else:
                terms = rows[root, word_index]
                for index, term in enumerate(terms):
                    formula.add(
                        (-term, *(terms[:index] + terms[index + 1:])),
                        "mixed_not_singleton",
                    )

    if pattern == "21":
        word0 = WORDS.index((0, 0, 0, 0))
        word1 = WORDS.index((1, 1, 1, 1))
        distinct_pair_vars = []
        for first in range(24):
            for second in range(24):
                if first == second:
                    continue
                pair = formula.variable()
                left = matching_vars[0, word0, first]
                right = matching_vars[0, word1, second]
                formula.add((-pair, left), "distinct_required_pair")
                formula.add((-pair, right), "distinct_required_pair")
                formula.add((pair, -left, -right), "distinct_required_pair")
                distinct_pair_vars.append(pair)
        formula.add(distinct_pair_vars, "distinct_required_pair_exists")

    for row in ROWS:
        for terminal in ROWS:
            if row == terminal:
                continue
            group = tuple(
                support_vars[bit]
                for bit in orthogonality_group(pattern, row, terminal)
            )
            for index, value in enumerate(group):
                formula.add(
                    (-value, *(group[:index] + group[index + 1:])),
                    "orthogonality_not_singleton",
                )

    support_literals = tuple(support_vars[bit] for bit in VALID_BITS)
    formula.at_most(support_literals, 20, "support_at_most_20")
    formula.at_most(
        tuple(-value for value in support_literals), 105 - 20,
        "support_at_least_20",
    )

    direct_clause_count = 0
    for root in ROWS:
        required_word_indices = tuple(
            index for index, word in enumerate(WORDS) if expected(pattern, root, word)
        )
        mixed_word_indices = tuple(
            index for index, word in enumerate(WORDS) if not expected(pattern, root, word)
        )
        mixed_pairs_by_key = {}
        for word_index in mixed_word_indices:
            for first in range(24):
                for second in range(first + 1, 24):
                    key = circuit_key(
                        MATCHING_BITS[root, word_index, first],
                        MATCHING_BITS[root, word_index, second],
                    )
                    mixed_pairs_by_key.setdefault(key, []).append(
                        (word_index, first, second)
                    )
        for word_index in required_word_indices:
            target_terms = rows[root, word_index]
            for first in range(24):
                for second in range(first + 1, 24):
                    if cycle_type(
                        PERMUTATIONS[root][first], PERMUTATIONS[root][second]
                    ) != (2,):
                        continue
                    key = circuit_key(
                        MATCHING_BITS[root, word_index, first],
                        MATCHING_BITS[root, word_index, second],
                    )
                    for mixed_word, mixed_first, mixed_second in mixed_pairs_by_key.get(key, ()):
                        mixed_terms = rows[root, mixed_word]
                        clause = (
                            -target_terms[first], -target_terms[second],
                            *(target_terms[index] for index in range(24) if index not in (first, second)),
                            -mixed_terms[mixed_first], -mixed_terms[mixed_second],
                            *(mixed_terms[index] for index in range(24) if index not in (mixed_first, mixed_second)),
                        )
                        formula.add(clause, "forbid_same_root_transposition_collision")
                        direct_clause_count += 1
    if direct_clause_count == 0:
        raise AssertionError("no direct-collision clauses generated")

    metadata = {
        "schema": "run084-pair-formula-v1",
        "pattern": pattern,
        "support_size": 20,
        "support_variable_count": len(support_vars),
        "matching_variable_count": len(matching_vars),
        "variable_count": formula.variable_count,
        "clause_count": len(formula.clauses),
        "clause_family_counts": dict(sorted(formula.family_counts.items())),
        "direct_collision_clause_count": direct_clause_count,
        "semantics": (
            "SAT preserves one exact finite countermodel; UNSAT with an "
            "independently checked LRAT proves this finite formula"
        ),
        "scope_boundary": (
            "one finite local chart and one case; no claim beyond the encoded scope"
        ),
    }
    return formula, metadata


def render_dimacs(formula: Formula) -> bytes:
    lines = [f"p cnf {formula.variable_count} {len(formula.clauses)}\n"]
    lines.extend(" ".join(map(str, clause)) + " 0\n" for clause in formula.clauses)
    return "".join(lines).encode("ascii")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pattern", required=True, choices=("111", "21"))
    parser.add_argument("--cnf", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()

    formula, metadata = build(args.pattern)
    dimacs = render_dimacs(formula)
    metadata["dimacs_sha256"] = hashlib.sha256(dimacs).hexdigest()
    canonical = json.dumps(metadata, sort_keys=True, separators=(",", ":"))
    metadata["canonical_outcome_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()

    args.cnf.write_bytes(dimacs)
    args.manifest.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
