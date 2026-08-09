#!/usr/bin/env python3
"""Exact integer-lattice audit of one accepted run-035 layer."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from sympy import Matrix
from sympy.matrices.normalforms import hermite_normal_form


DEFAULT_AUDIT_RUN = "run-038"
DEFAULT_SOURCE_RUN = 31314627849
DEFAULT_SOURCE_LOGICAL_RUN = "run-035"


def edge(a, b):
    return (a, b) if a < b else (b, a)


def matchings(vertices, allowed):
    if not vertices:
        return [()]
    first, result = vertices[0], []
    for other in vertices[1:]:
        item = edge(first, other)
        if item in allowed:
            rest = tuple(value for value in vertices if value not in (first, other))
            result.extend((item, *tail) for tail in matchings(rest, allowed))
    return result


def states(order):
    result = []
    for number in range(81):
        value, state = number, {}
        for vertex in order:
            state[vertex] = value % 3
            value //= 3
        result.append(state)
    return tuple(result)


class CycleSystem:
    def __init__(self, order, residual, residual_index, masks):
        self.order = tuple(order)
        cycle_edges = tuple(item for item in residual if item[0] in self.order and item[1] in self.order)
        if len(matchings(self.order, set(cycle_edges))) != 2:
            raise ValueError("context does not describe a two-matching cycle")
        self.keys = tuple(
            (item, row, column)
            for item in cycle_edges
            for row in range(3)
            for column in range(3)
            if masks[residual_index[item]] & (1 << (3 * row + column))
        )
        key_index = {key: index for index, key in enumerate(self.keys)}
        terms = []
        for state in states(self.order):
            state_terms = []
            for matching in matchings(self.order, set(cycle_edges)):
                exponent, active = [0] * len(self.keys), True
                for item in matching:
                    position = key_index.get((item, state[item[0]], state[item[1]]))
                    if position is None:
                        active = False
                        break
                    exponent[position] += 1
                if active:
                    state_terms.append(tuple(exponent))
            terms.append(tuple(state_terms))
        self.terms = tuple(terms)
        self.forced = sum(1 << index for index, values in enumerate(self.terms) if len(values) == 1)
        self.cache = {}

    def relation(self, index):
        first, second = self.terms[index]
        return tuple(a - b for a, b in zip(first, second)) + (-1,)

    def potential(self, allowed):
        cached = self.cache.get(allowed)
        if cached is not None:
            return cached
        generators = {self.relation(index) for index, values in enumerate(self.terms) if not (allowed >> index & 1) and len(values) == 2}
        generators.add((0,) * len(self.keys) + (2,))
        hnf = hermite_normal_form(Matrix(sorted(generators)).T)
        pivot_rows = hnf.T.rref()[1]
        inverse_minor = hnf.extract(pivot_rows, range(hnf.cols)).inv()

        def member(vector):
            target = Matrix(vector)
            coordinates = inverse_minor * Matrix([vector[index] for index in pivot_rows])
            return all(value.q == 1 for value in coordinates) and hnf * coordinates == target

        if member((0,) * len(self.keys) + (1,)):
            result = (0, True)
        else:
            possible = 0
            for index, values in enumerate(self.terms):
                if allowed >> index & 1 and values and (len(values) == 1 or not member(self.relation(index))):
                    possible |= 1 << index
            result = (possible, False)
        self.cache[allowed] = result
        return result

    @staticmethod
    def coordinate_face(bits):
        indices = [index for index in range(81) if bits >> index & 1]
        fixed = []
        for position in range(4):
            values = {(index // (3 ** position)) % 3 for index in indices}
            if len(values) == 1:
                fixed.append(position)
        return len(indices) == 9 and set(fixed) in ({0, 1}, {1, 2}, {2, 3}, {0, 3})


def checked_input(
    path,
    expected_index,
    expected_orbit,
    expected_support,
    expected_missing_type,
    source_run,
    source_logical_run,
):
    stored = json.loads(path.read_text(encoding="utf-8"))
    required = ("support", "orbit", "raw_supports", "support_orbits", "orbits")
    if any(field not in stored for field in required):
        raise ValueError("input misses required exact-enumeration fields")
    index = stored.get("index", stored.get("case"))
    if index != expected_index or stored.get("orbit") != expected_orbit:
        raise ValueError("input layer has an unexpected source identity")
    if stored.get("missing_type", expected_missing_type) != expected_missing_type:
        raise ValueError("input layer has an unexpected source type")
    if stored["support"] != expected_support:
        raise ValueError("input layer does not match the declared matrix cell")
    if stored.get("source_run") not in (None, source_run):
        raise ValueError("input layer names a different source run")
    if stored.get("run_id") not in (None, source_logical_run):
        raise ValueError("input layer names a different logical run")
    if "complete_exact_coverage" in stored:
        if not stored["complete_exact_coverage"] or stored.get("status") != "SUCCESS" or stored.get("errors"):
            raise ValueError("merged native input is incomplete")
        workers = stored.get("workers")
        if not isinstance(workers, list) or len(workers) != 4:
            raise ValueError("merged native input has invalid worker coverage")
        for worker in workers:
            if worker.get("exit_code") != 0 or not worker.get("complete_enumeration"):
                raise ValueError("merged native input contains an incomplete worker")
            if worker.get("status") not in ("OPTIMAL", "INFEASIBLE"):
                raise ValueError("merged native input contains a nonterminal worker")
    else:
        exact_fields = ("complete_enumeration", "hit_cap", "hit_deadline")
        if any(field not in stored for field in exact_fields):
            raise ValueError("standard input misses exact-enumeration fields")
        if not stored["complete_enumeration"] or stored["hit_cap"] or stored["hit_deadline"]:
            raise ValueError("standard input is incomplete")
    if len(stored["orbits"]) != stored["support_orbits"]:
        raise ValueError("support-orbit count mismatch")
    if sum(item["labelled_multiplicity"] for item in stored["orbits"]) != stored["raw_supports"]:
        raise ValueError("labelled multiplicity mismatch")
    seen = set()
    for item in stored["orbits"]:
        masks = item.get("masks")
        if not isinstance(masks, list) or len(masks) != 8:
            raise ValueError("support orbit has an invalid mask vector")
        if any(not isinstance(mask, int) or mask < 0 or mask >= 512 for mask in masks):
            raise ValueError("support orbit has an out-of-range mask")
        if sum(mask.bit_count() for mask in masks) != expected_support:
            raise ValueError("support orbit has the wrong total support")
        key = tuple(masks)
        if key in seen:
            raise ValueError("duplicate support-orbit representative")
        seen.add(key)
        if not isinstance(item.get("labelled_multiplicity"), int) or item["labelled_multiplicity"] <= 0:
            raise ValueError("support orbit has an invalid labelled multiplicity")
    stored["index"] = index
    stored["missing_type"] = stored.get("missing_type", expected_missing_type)
    return stored


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--context", required=True, type=Path)
    parser.add_argument("--run-id", default=DEFAULT_AUDIT_RUN)
    parser.add_argument("--source-run", type=int, default=DEFAULT_SOURCE_RUN)
    parser.add_argument("--source-logical-run", default=DEFAULT_SOURCE_LOGICAL_RUN)
    parser.add_argument("--expected-index", required=True, type=int)
    parser.add_argument("--expected-orbit", required=True, type=int)
    parser.add_argument("--expected-support", required=True, type=int)
    parser.add_argument("--expected-missing-type", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    context_records = json.loads(args.context.read_text(encoding="utf-8"))["records"]
    contexts = {item["index"]: item for item in context_records}
    if len(contexts) != len(context_records):
        raise ValueError("duplicate context index")
    context = contexts.get(args.expected_index)
    if not context or context["orbit"] != args.expected_orbit or context["missing_type"] != args.expected_missing_type:
        raise ValueError("context identity mismatch")
    stored = checked_input(
        args.input,
        args.expected_index,
        args.expected_orbit,
        args.expected_support,
        args.expected_missing_type,
        args.source_run,
        args.source_logical_run,
    )
    residual = tuple(edge(*item) for item in context["residual_edges"])
    residual_index = {item: index for index, item in enumerate(residual)}
    concepts = tuple((int(left), int(right)) for left, right in context["concepts"])
    histogram = Counter()
    two_sided_samples, nonface_samples = [], []
    two_sided_support_orbits = nonface_support_orbits = 0
    two_sided_total = nonface_total = 0
    for support_orbit, support_record in enumerate(stored["orbits"]):
        masks = tuple(support_record["masks"])
        if len(masks) != len(residual):
            raise ValueError("mask count mismatch")
        systems = tuple(CycleSystem(order, residual, residual_index, masks) for order in context["cycle_orders"])
        two_sided, orbit_has_nonface = 0, False
        for allowed_a, allowed_b in concepts:
            if systems[0].forced & ~allowed_a or systems[1].forced & ~allowed_b:
                continue
            possible_a, bad_a = systems[0].potential(allowed_a)
            possible_b, bad_b = systems[1].potential(allowed_b)
            if not bad_a and not bad_b and possible_a and possible_b:
                two_sided += 1
                is_face = CycleSystem.coordinate_face(possible_a) and CycleSystem.coordinate_face(possible_b)
                if len(two_sided_samples) < 5:
                    two_sided_samples.append({"support_orbit": support_orbit, "two_sided": two_sided, "coordinate_edge_face": is_face})
                if not is_face:
                    nonface_total += 1
                    if not orbit_has_nonface and len(nonface_samples) < 5:
                        nonface_samples.append({"support_orbit": support_orbit, "two_sided": two_sided})
                    orbit_has_nonface = True
        histogram[two_sided] += 1
        two_sided_total += two_sided
        two_sided_support_orbits += bool(two_sided)
        nonface_support_orbits += orbit_has_nonface
    result = {
        "schema_version": 1,
        "run_id": args.run_id,
        "source_run": args.source_run,
        "source_logical_run": args.source_logical_run,
        "index": stored["index"],
        "orbit": stored["orbit"],
        "missing_type": stored["missing_type"],
        "support": stored["support"],
        "input_complete": True,
        "audited_support_orbits": stored["support_orbits"],
        "two_sided_total": two_sided_total,
        "two_sided_support_orbits": two_sided_support_orbits,
        "two_sided_histogram": [
            {"two_sided": key, "orbits": histogram[key]} for key in sorted(histogram)
        ],
        "two_sided_samples": two_sided_samples,
        "nonface_total": nonface_total,
        "nonface_support_orbits": nonface_support_orbits,
        "nonface_samples": nonface_samples,
        "all_force_zero": two_sided_total == 0,
        "all_two_sided_are_coordinate_edge_faces": nonface_total == 0,
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
