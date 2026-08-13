#!/usr/bin/env python3
"""Emit and directly replay one neutral proof-class formula."""

from __future__ import annotations

import argparse
import hashlib
from itertools import combinations
import json
from pathlib import Path


V = tuple(range(8))
COLORS = tuple(range(3))
R = ((0, 2), (1, 3), (4, 6), (5, 7))
CROSS = tuple((left, right) for left in range(4) for right in range(4, 8))
EDGES = tuple(sorted(R + CROSS))
OFF = tuple((a, b) for a in COLORS for b in COLORS if a != b)


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def class_record(source, class_id):
    records = [record for record in source["classes"] if record["class_id"] == class_id]
    if len(records) != 1 or class_id == 0 or records[0]["already_certified"]:
        raise ValueError("requested class is absent or outside the new proof family")
    record = records[0]
    if len(record["counts"]) != 4 or sum(record["counts"]) != 5:
        raise ValueError("malformed class counts")
    return record


def matching_catalogue():
    output = []
    for candidate in combinations(EDGES, 4):
        mask = 0
        valid = True
        for u, v in candidate:
            endpoints = (1 << u) | (1 << v)
            if mask & endpoints:
                valid = False
                break
            mask |= endpoints
        if valid and mask == 255:
            output.append(tuple(sorted(candidate)))
    output = tuple(sorted(output))
    if len(output) != 33:
        raise AssertionError("unexpected matching count")
    return output


def decode(state):
    return tuple((state // 3 ** vertex) % 3 for vertex in V)


class Formula:
    def __init__(self):
        self.names = []
        self.lookup = {}
        self.clauses = []

    def new(self, name):
        if name in self.lookup:
            raise ValueError("duplicate variable")
        self.names.append(name)
        self.lookup[name] = len(self.names)
        return len(self.names)

    def add(self, *values):
        clause = tuple(int(value) for value in values)
        if not clause or len(clause) != len(set(clause)) or any(-value in clause for value in clause):
            raise ValueError("noncanonical input clause")
        if any(value == 0 or abs(value) > len(self.names) for value in clause):
            raise ValueError("literal outside allocated range")
        self.clauses.append(clause)


def exact_count(formula, variables, count):
    for subset in combinations(variables, count + 1):
        formula.add(*(-value for value in subset))
    for subset in combinations(variables, len(variables) - count + 1):
        formula.add(*subset)


def build(counts):
    matchings = matching_catalogue()
    pure = tuple(sorted(R))
    formula = Formula()
    x = {(edge, a, b): formula.new(f"x_{edge[0]}_{edge[1]}_{a}_{b}") for edge in CROSS for a in COLORS for b in COLORS}
    r = {(edge, a, b): formula.new(f"r_{edge[0]}_{edge[1]}_{a}_{b}") for edge in R for a, b in OFF}
    for edge, count in zip(R, counts, strict=True):
        exact_count(formula, [r[edge, a, b] for a, b in OFF], count)
    for edge in CROSS:
        formula.add(*(x[edge, a, b] for a in COLORS for b in COLORS))
    for q in COLORS:
        for matching in matchings:
            if matching != pure:
                formula.add(*(-x[edge, q, q] for edge in matching if edge in CROSS))
    for root in V:
        incident = tuple(edge for edge in CROSS if root in edge)
        for q in COLORS:
            witnesses = []
            for edge in incident:
                h = formula.new(f"h_{root}_{q}_{edge[0]}_{edge[1]}")
                witnesses.append(h)
                if root < 4:
                    inside = [x[edge, a, q] for a in COLORS]
                    outside = [x[edge, a, b] for a in COLORS for b in COLORS if b != q]
                else:
                    inside = [x[edge, q, b] for b in COLORS]
                    outside = [x[edge, a, b] for a in COLORS for b in COLORS if a != q]
                formula.add(-h, *inside)
                for value in outside:
                    formula.add(-h, -value)
                for value in inside:
                    formula.add(-value, *outside, h)
            formula.add(*witnesses)
    for root in V:
        r_edge = next(edge for edge in R if root in edge)
        incident = tuple(edge for edge in CROSS if root in edge)
        for q in COLORS:
            sr = formula.new(f"sr_{root}_{q}")
            contaminants = ([r[r_edge, q, b] for b in COLORS if b != q] if root == r_edge[0]
                            else [r[r_edge, a, q] for a in COLORS if a != q])
            for value in contaminants:
                formula.add(-sr, -value)
            formula.add(sr, *contaminants)
            witnesses = [sr]
            for edge in incident:
                s = formula.new(f"s_{root}_{q}_{edge[0]}_{edge[1]}")
                witnesses.append(s)
                same = x[edge, q, q]
                other = ([x[edge, q, b] for b in COLORS if b != q] if root < 4
                         else [x[edge, a, q] for a in COLORS if a != q])
                formula.add(-s, same)
                for value in other:
                    formula.add(-s, -value)
                formula.add(-same, *other, s)
            formula.add(*witnesses)
    for state in range(3 ** 8):
        colours = decode(state)
        if len(set(colours)) == 1:
            continue
        terms = []
        constant = False
        for matching_id, matching in enumerate(matchings):
            required = []
            for edge in matching:
                a, b = colours[edge[0]], colours[edge[1]]
                if edge in R:
                    if a != b:
                        required.append(r[edge, a, b])
                else:
                    required.append(x[edge, a, b])
            if not required:
                if constant:
                    raise AssertionError("two constant terms")
                constant = True
                continue
            term = formula.new(f"t_{state}_{matching_id}")
            for value in required:
                formula.add(-term, value)
            formula.add(term, *(-value for value in required))
            terms.append(term)
        if constant:
            formula.add(*terms)
        else:
            for index, term in enumerate(terms):
                formula.add(-term, *(terms[:index] + terms[index + 1:]))
    return formula


def emit(input_path, class_id, cnf_path, metadata_path):
    source = load(input_path)
    record = class_record(source, class_id)
    formula = build(tuple(record["counts"]))
    with cnf_path.open("w", encoding="ascii", newline="\n", buffering=1024 * 1024) as output:
        output.write(f"p cnf {len(formula.names)} {len(formula.clauses)}\n")
        for clause in formula.clauses:
            output.write(" ".join(map(str, clause)) + " 0\n")
    metadata = {
        "schema": "neutral-proof-class-formula-v1",
        "class_id": class_id,
        "counts": record["counts"],
        "support_orbits": record["support_orbits"],
        "support_placements": record["support_placements"],
        "input_sha256": sha(input_path),
        "variable_count": len(formula.names),
        "clause_count": len(formula.clauses),
        "variable_names_sha256": hashlib.sha256(json.dumps(formula.names, separators=(",", ":")).encode()).hexdigest(),
        "clauses_sha256": hashlib.sha256(json.dumps([list(c) for c in formula.clauses], separators=(",", ":")).encode()).hexdigest(),
        "cnf_sha256": sha(cnf_path),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({key: metadata[key] for key in ("class_id", "variable_count", "clause_count", "cnf_sha256")}, sort_keys=True))


def parse_model(path):
    positive = set()
    saw_sat = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("s SATISFIABLE"):
            saw_sat = True
        if not line.startswith("v"):
            continue
        for word in line[1:].split():
            literal = int(word)
            if literal > 0:
                positive.add(literal)
    if not saw_sat:
        raise ValueError("solver log is not SATISFIABLE")
    return positive


def direct_replay(counts, positive):
    cross = set()
    variable = 1
    masks = []
    for edge in CROSS:
        mask = 0
        for a in COLORS:
            for b in COLORS:
                if variable in positive:
                    cross.add((edge, a, b))
                    mask |= 1 << (3 * a + b)
                variable += 1
        if not mask:
            raise ValueError("SAT support has an empty cross edge")
        masks.append({"edge": list(edge), "mask": mask})
    r_support = {edge: {(q, q) for q in COLORS} for edge in R}
    r_entries = []
    for edge in R:
        for a, b in OFF:
            if variable in positive:
                r_support[edge].add((a, b))
                r_entries.append({"edge": list(edge), "a": a, "b": b})
            variable += 1
    actual_counts = [len(r_support[edge]) - 3 for edge in R]
    if actual_counts != counts:
        raise ValueError("SAT support violates exact edge counts")
    matchings = matching_catalogue()
    pure_counts = {}
    for q in COLORS:
        pure_counts[str(q)] = sum(all((q, q) in r_support[edge] if edge in R else (edge, q, q) in cross for edge in matching) for matching in matchings)
    if set(pure_counts.values()) != {1}:
        raise ValueError("SAT support violates unique pure matching")
    star_missing = []
    full_missing = []
    for root in V:
        for q in COLORS:
            star = False
            for edge in R + CROSS:
                if root not in edge:
                    continue
                entries = r_support[edge] if edge in R else {(a, b) for current, a, b in cross if current == edge}
                row = {(a, b) for a, b in entries if (a if root == edge[0] else b) == q}
                star |= row == {(q, q)}
            if not star:
                star_missing.append([root, q])
            full = False
            for edge in CROSS:
                if root not in edge:
                    continue
                entries = {(a, b) for current, a, b in cross if current == edge}
                column = {(a, b) for a, b in entries if (b if root == edge[0] else a) == q}
                full |= bool(column) and len(column) == len(entries)
            if not full:
                full_missing.append([root, q])
    singleton_states = []
    histogram = {}
    for state in range(3 ** 8):
        colours = decode(state)
        if len(set(colours)) == 1:
            continue
        count = 0
        for matching in matchings:
            valid = all(((colours[edge[0]], colours[edge[1]]) in r_support[edge]) if edge in R
                        else ((edge, colours[edge[0]], colours[edge[1]]) in cross) for edge in matching)
            count += valid
        histogram[str(count)] = histogram.get(str(count), 0) + 1
        if count == 1:
            singleton_states.append(state)
    if star_missing or full_missing or singleton_states:
        raise ValueError("SAT support fails direct semantic replay")
    return {
        "pure_matching_counts": pure_counts,
        "star_missing": star_missing,
        "full_column_missing": full_missing,
        "mixed_matching_histogram": dict(sorted(histogram.items(), key=lambda item: int(item[0]))),
        "singleton_states": singleton_states,
        "R_entries": r_entries,
        "cross_edge_masks": masks,
    }


def replay(input_path, class_id, model_path, output_path):
    source = load(input_path)
    record = class_record(source, class_id)
    result = direct_replay(record["counts"], parse_model(model_path))
    payload = {
        "schema": "neutral-proof-class-positive-v1",
        "class_id": class_id,
        "counts": record["counts"],
        "input_sha256": sha(input_path),
        "direct_replay_accepted": True,
        **result,
    }
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"class_id": class_id, "direct_replay_accepted": True}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    emit_parser = sub.add_parser("emit")
    emit_parser.add_argument("--input", type=Path, required=True)
    emit_parser.add_argument("--class-id", type=int, required=True)
    emit_parser.add_argument("--cnf", type=Path, required=True)
    emit_parser.add_argument("--metadata", type=Path, required=True)
    replay_parser = sub.add_parser("replay")
    replay_parser.add_argument("--input", type=Path, required=True)
    replay_parser.add_argument("--class-id", type=int, required=True)
    replay_parser.add_argument("--model", type=Path, required=True)
    replay_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "emit":
        emit(args.input, args.class_id, args.cnf, args.metadata)
    else:
        replay(args.input, args.class_id, args.model, args.output)


if __name__ == "__main__":
    main()
