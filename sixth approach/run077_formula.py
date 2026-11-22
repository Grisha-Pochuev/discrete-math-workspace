#!/usr/bin/env python3
"""Emit and directly replay one neutral residual support formula."""

from __future__ import annotations

import argparse
import hashlib
from itertools import combinations
import json
from pathlib import Path

import run076_formula as calibrated


V = calibrated.V
COLORS = calibrated.COLORS
R = calibrated.R
CROSS = calibrated.CROSS
EDGES = frozenset(R + CROSS)
OFF = calibrated.OFF
R_SET = frozenset(R)
CROSS_SET = frozenset(CROSS)


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def exact_clauses(variables, count):
    output = []
    for subset in combinations(variables, count + 1):
        output.append(tuple(-value for value in subset))
    for subset in combinations(variables, len(variables) - count + 1):
        output.append(tuple(subset))
    return output


def support_literal(formula, truth, root, neighbor, root_color, neighbor_color):
    edge = tuple(sorted((root, neighbor)))
    ordered = (
        (root_color, neighbor_color) if root < neighbor
        else (neighbor_color, root_color)
    )
    if edge in CROSS_SET:
        return formula.lookup[
            f"x_{edge[0]}_{edge[1]}_{ordered[0]}_{ordered[1]}"
        ]
    if edge in R_SET:
        if ordered[0] == ordered[1]:
            return truth
        return formula.lookup[
            f"r_{edge[0]}_{edge[1]}_{ordered[0]}_{ordered[1]}"
        ]
    raise AssertionError("entry outside fixed skeleton")


def gate_or(formula, name, values):
    values = tuple(values)
    output = formula.new(name)
    for value in values:
        formula.add(-value, output)
    formula.add(-output, *values)
    return output


def gate_and(formula, name, values):
    values = tuple(values)
    output = formula.new(name)
    for value in values:
        formula.add(-output, value)
    formula.add(output, *(-value for value in values))
    return output


def gate_not(formula, name, value):
    output = formula.new(name)
    formula.add(output, value)
    formula.add(-output, -value)
    return output


def add_pair_conditions(formula):
    truth = formula.new("pp_const_true")
    formula.add(truth)
    assertions = 0
    for root in V:
        neighbors = tuple(
            vertex for vertex in V
            if vertex != root and tuple(sorted((root, vertex))) in EDGES
        )
        if len(neighbors) != 5:
            raise AssertionError("unexpected degree")
        for first, second in combinations(COLORS, 2):
            pair = (first, second)
            pure_by_output = {first: [], second: []}
            for output in pair:
                for neighbor in neighbors:
                    prefix = f"pp_{root}_{first}_{second}_{output}_{neighbor}"
                    target = [
                        support_literal(
                            formula, truth, root, neighbor, root_color, output
                        )
                        for root_color in pair
                    ]
                    contamination = [
                        support_literal(
                            formula, truth, root, neighbor, root_color, other
                        )
                        for root_color in pair
                        for other in COLORS
                        if other != output
                    ]
                    has = gate_or(formula, f"{prefix}_has", target)
                    dirty = gate_or(
                        formula, f"{prefix}_contaminated", contamination
                    )
                    clean = gate_not(formula, f"{prefix}_clean", dirty)
                    pure = gate_and(formula, f"{prefix}_pure", (has, clean))
                    pure_by_output[output].append(pure)
            has_first = gate_or(
                formula, f"pp_{root}_{first}_{second}_has_pure_{first}",
                pure_by_output[first],
            )
            has_second = gate_or(
                formula, f"pp_{root}_{first}_{second}_has_pure_{second}",
                pure_by_output[second],
            )
            both = gate_and(
                formula, f"pp_{root}_{first}_{second}_both_pure",
                (has_first, has_second),
            )
            outside = [
                support_literal(
                    formula, truth, root, neighbor, root_color, other
                )
                for neighbor in neighbors
                for root_color in pair
                for other in COLORS
                if other not in pair
            ]
            leaves = gate_or(
                formula, f"pp_{root}_{first}_{second}_leaves", outside
            )
            preserved = gate_not(
                formula, f"pp_{root}_{first}_{second}_preserved", leaves
            )
            formula.add(both, preserved)
            assertions += 1
    if assertions != 24:
        raise AssertionError("pair-condition assertion count differs")


def build():
    source = calibrated.build((0, 0, 1, 4))
    r_variables = [
        source.lookup[f"r_{edge[0]}_{edge[1]}_{a}_{b}"]
        for edge in R for a, b in OFF
    ]
    prefix = []
    for edge, count in zip(R, (0, 0, 1, 4), strict=True):
        edge_variables = [
            source.lookup[f"r_{edge[0]}_{edge[1]}_{a}_{b}"]
            for a, b in OFF
        ]
        prefix.extend(exact_clauses(edge_variables, count))
    if source.clauses[:len(prefix)] != prefix:
        raise AssertionError("calibration prefix differs")

    formula = calibrated.Formula()
    for name in source.names:
        formula.new(name)
    for clause in source.clauses[len(prefix):]:
        formula.add(*clause)
    common_count = len(formula.clauses)
    for clause in combinations(r_variables, 20):
        formula.add(*clause)
    lower_bound_count = len(formula.clauses) - common_count
    add_pair_conditions(formula)
    if common_count != 1253806 or lower_bound_count != 10626:
        raise AssertionError("residual formula census differs")
    return formula, common_count, lower_bound_count


def validate_spec(spec):
    required = {
        "schema": "neutral-proof-residue-v1",
        "run_id": "run-077",
        "lower_bound": 5,
        "expected_variable_count": 217801,
        "expected_clause_count": 1268249,
        "expected_cnf_sha256": "75a424598feac97f9eead14f5de24268853822aa65546eac53cab75e85e04b82",
    }
    for key, value in required.items():
        if spec.get(key) != value:
            raise ValueError(f"spec identity differs: {key}")


def emit(spec_path, cnf_path, metadata_path):
    spec = load(spec_path)
    validate_spec(spec)
    formula, common_count, lower_bound_count = build()
    with cnf_path.open("w", encoding="ascii", newline="\n", buffering=1024 * 1024) as output:
        output.write(f"p cnf {len(formula.names)} {len(formula.clauses)}\n")
        for clause in formula.clauses:
            output.write(" ".join(map(str, clause)) + " 0\n")
    metadata = {
        "schema": "neutral-proof-residue-formula-v1",
        "lower_bound": 5,
        "common_clause_count": common_count,
        "lower_bound_clause_count": lower_bound_count,
        "pair_condition_assertion_count": 24,
        "spec_sha256": sha(spec_path),
        "variable_count": len(formula.names),
        "clause_count": len(formula.clauses),
        "variable_names_sha256": hashlib.sha256(
            json.dumps(formula.names, separators=(",", ":")).encode()
        ).hexdigest(),
        "clauses_sha256": hashlib.sha256(
            json.dumps([list(c) for c in formula.clauses], separators=(",", ":")).encode()
        ).hexdigest(),
        "cnf_sha256": sha(cnf_path),
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(json.dumps({
        key: metadata[key]
        for key in ("variable_count", "clause_count", "cnf_sha256")
    }, sort_keys=True))


def parse_model(path):
    positive = set()
    saw_sat = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("s SATISFIABLE"):
            saw_sat = True
        if line.startswith("v"):
            positive.update(
                literal for literal in map(int, line[1:].split())
                if literal > 0
            )
    if not saw_sat:
        raise ValueError("solver log is not SATISFIABLE")
    return positive


def entry_present(cross, r_support, root, neighbor, root_color, neighbor_color):
    edge = tuple(sorted((root, neighbor)))
    ordered = (
        (root_color, neighbor_color) if root < neighbor
        else (neighbor_color, root_color)
    )
    return (
        (edge, ordered[0], ordered[1]) in cross if edge in CROSS_SET
        else ordered in r_support[edge]
    )


def direct_replay(positive):
    formula, _, _ = build()
    if not all(any(
        (literal > 0 and literal in positive) or
        (literal < 0 and -literal not in positive)
        for literal in clause
    ) for clause in formula.clauses):
        raise ValueError("SAT assignment does not satisfy emitted CNF")

    cross = set()
    masks = []
    variable = 1
    for edge in CROSS:
        mask = 0
        for a in COLORS:
            for b in COLORS:
                if variable in positive:
                    cross.add((edge, a, b))
                    mask |= 1 << (3 * a + b)
                variable += 1
        if mask == 0:
            raise ValueError("empty cross edge")
        masks.append({"edge": list(edge), "mask": mask})
    r_support = {edge: {(q, q) for q in COLORS} for edge in R}
    r_entries = []
    for edge in R:
        for a, b in OFF:
            if variable in positive:
                r_support[edge].add((a, b))
                r_entries.append({"edge": list(edge), "a": a, "b": b})
            variable += 1
    if len(r_entries) < 5:
        raise ValueError("lower bound violated")

    matchings = calibrated.matching_catalogue()
    pure_counts = {
        str(q): sum(all(
            ((q, q) in r_support[edge]) if edge in R_SET
            else ((edge, q, q) in cross)
            for edge in matching
        ) for matching in matchings)
        for q in COLORS
    }
    if set(pure_counts.values()) != {1}:
        raise ValueError("pure matching count differs")

    star_missing = []
    full_missing = []
    pair_missing = []
    for root in V:
        neighbors = tuple(
            neighbor for neighbor in V
            if neighbor != root and tuple(sorted((root, neighbor))) in EDGES
        )
        for q in COLORS:
            star = any(
                entry_present(cross, r_support, root, neighbor, q, q) and
                all(not entry_present(cross, r_support, root, neighbor, q, other)
                    for other in COLORS if other != q)
                for neighbor in neighbors
            )
            if not star:
                star_missing.append([root, q])
            full = any(
                any(entry_present(cross, r_support, root, neighbor, a, q) for a in COLORS) and
                all(not entry_present(cross, r_support, root, neighbor, a, other)
                    for a in COLORS for other in COLORS if other != q)
                for neighbor in neighbors
            )
            if not full:
                full_missing.append([root, q])
        for first, second in combinations(COLORS, 2):
            pair = (first, second)
            pure_outputs = []
            for output in pair:
                pure_outputs.append(any(
                    any(entry_present(cross, r_support, root, neighbor, a, output) for a in pair) and
                    all(not entry_present(cross, r_support, root, neighbor, a, other)
                        for a in pair for other in COLORS if other != output)
                    for neighbor in neighbors
                ))
            preserved = all(
                not entry_present(cross, r_support, root, neighbor, a, other)
                for neighbor in neighbors for a in pair
                for other in COLORS if other not in pair
            )
            if not (all(pure_outputs) or preserved):
                pair_missing.append([root, first, second])

    singleton_states = []
    histogram = {}
    for state in range(3 ** 8):
        colours = calibrated.decode(state)
        if len(set(colours)) == 1:
            continue
        count = sum(all(
            ((colours[edge[0]], colours[edge[1]]) in r_support[edge])
            if edge in R_SET else
            ((edge, colours[edge[0]], colours[edge[1]]) in cross)
            for edge in matching
        ) for matching in matchings)
        histogram[str(count)] = histogram.get(str(count), 0) + 1
        if count == 1:
            singleton_states.append(state)
    if star_missing or full_missing or pair_missing or singleton_states:
        raise ValueError("direct semantic replay failed")
    return {
        "R_offdiagonal_count": len(r_entries),
        "R_entries": r_entries,
        "cross_edge_masks": masks,
        "pure_matching_counts": pure_counts,
        "star_missing": star_missing,
        "full_column_missing": full_missing,
        "pair_condition_missing": pair_missing,
        "mixed_matching_histogram": dict(
            sorted(histogram.items(), key=lambda item: int(item[0]))
        ),
        "singleton_states": singleton_states,
    }


def replay(spec_path, model_path, output_path):
    spec = load(spec_path)
    validate_spec(spec)
    result = direct_replay(parse_model(model_path))
    payload = {
        "schema": "neutral-proof-residue-positive-v1",
        "spec_sha256": sha(spec_path),
        "direct_replay_accepted": True,
        **result,
    }
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(json.dumps({
        "direct_replay_accepted": True,
        "R_offdiagonal_count": result["R_offdiagonal_count"],
    }, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    emit_parser = sub.add_parser("emit")
    emit_parser.add_argument("--spec", type=Path, required=True)
    emit_parser.add_argument("--cnf", type=Path, required=True)
    emit_parser.add_argument("--metadata", type=Path, required=True)
    replay_parser = sub.add_parser("replay")
    replay_parser.add_argument("--spec", type=Path, required=True)
    replay_parser.add_argument("--model", type=Path, required=True)
    replay_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "emit":
        emit(args.spec, args.cnf, args.metadata)
    else:
        replay(args.spec, args.model, args.output)


if __name__ == "__main__":
    main()

