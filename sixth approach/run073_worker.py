#!/usr/bin/env python3
"""Minimize support while forbidding every direct two-row obstruction."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import ctypes
from ctypes import wintypes
import hashlib
import itertools
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / ".local-tools" / "ortools-runtime2"))

from ortools.sat.python import cp_model

from run073_logic import (
    add_exact_cardinality_indicator,
    add_group_conflict,
    add_pair_to_group_implication,
)


N = 8


def perfect_matchings(vertices):
    vertices = tuple(sorted(vertices))
    if not vertices:
        yield ()
        return
    first = vertices[0]
    for second in vertices[1:]:
        rest = tuple(vertex for vertex in vertices if vertex not in (first, second))
        for tail in perfect_matchings(rest):
            yield tuple(sorted(((first, second),) + tail))


ALL_MATCHINGS = tuple(sorted(perfect_matchings(range(N))))


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def working_set_mib():
    if sys.platform != "win32":
        try:
            for line in Path("/proc/self/status").read_text(encoding="ascii").splitlines():
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024.0
        except (OSError, ValueError, IndexError):
            return 0.0
        return 0.0
    class Counters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    handle = ctypes.windll.kernel32.GetCurrentProcess()
    query = ctypes.windll.kernel32.K32GetProcessMemoryInfo
    query.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    query.restype = wintypes.BOOL
    if not query(handle, ctypes.byref(counters), counters.cb):
        return 0.0
    return counters.WorkingSetSize / (1024 * 1024)


def check_memory(limit_mib, phase):
    current = working_set_mib()
    if limit_mib and current > limit_mib:
        raise MemoryError(f"working-set guard exceeded during {phase}: {current:.1f} MiB > {limit_mib} MiB")
    return current


def compact(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def decode(index):
    values = []
    for _ in range(N):
        values.append(index % 3)
        index //= 3
    return tuple(values)


def ratio_key(left, right):
    counts = Counter(left)
    counts.subtract(right)
    vector = tuple(sorted((entry, count) for entry, count in counts.items() if count))
    negative = tuple((entry, -count) for entry, count in vector)
    return min(vector, negative)


def serialise_ratio(ratio):
    return [
        [[list(entry[0]), entry[1], entry[2]], multiplicity]
        for entry, multiplicity in ratio
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path)
    parser.add_argument("--search-id")
    parser.add_argument("--types", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--manifest-acceptance", type=Path)
    parser.add_argument("--seconds", type=float, default=360.0)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--random-seed", type=int, default=3)
    parser.add_argument("--randomize-search", action="store_true")
    parser.add_argument("--objective-upper-bound", type=int)
    parser.add_argument("--memory-limit-mib", type=float, default=0.0)
    parser.add_argument("--dense-hint", action="store_true")
    parser.add_argument("--support-hint", type=Path)
    parser.add_argument("--fix-dense-support", action="store_true")
    parser.add_argument("--fixed-support", type=Path)
    parser.add_argument("--event-no-good", type=Path, action="append", default=[])
    parser.add_argument("--event-acceptance", type=Path, action="append", default=[])
    parser.add_argument("--rectangle-bundle", type=Path, action="append", default=[])
    parser.add_argument("--rectangle-acceptance", type=Path, action="append", default=[])
    parser.add_argument("--symmetry-bundle", type=Path, action="append", default=[])
    parser.add_argument("--symmetry-acceptance", type=Path, action="append", default=[])
    parser.add_argument("--pairing-audit", type=Path, action="append", default=[])
    parser.add_argument("--pairing-acceptance", type=Path, action="append", default=[])
    parser.add_argument("--pairing-symmetry-bundle", type=Path, action="append", default=[])
    parser.add_argument("--pairing-symmetry-acceptance", type=Path, action="append", default=[])
    parser.add_argument("--cascade-aggregate-state", type=int, action="append", default=[])
    parser.add_argument("--cascade-all-mixed-states", action="store_true")
    parser.add_argument("--disable-presolve", action="store_true")
    parser.add_argument("--stop-after-first-solution", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.spec:
        if not args.search_id:
            raise AssertionError("--spec requires --search-id")
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
        search = next((item for item in spec["searches"] if item["id"] == args.search_id), None)
        if search is None:
            raise AssertionError("search id is absent from immutable spec")
        repo_root = args.spec.resolve().parents[2]
        args.types = repo_root / spec["files"]["types"]
        args.manifest = repo_root / spec["files"]["input"]
        args.manifest_acceptance = repo_root / spec["files"]["input_acceptance"]
        args.seconds = float(search["seconds"])
        args.workers = int(search["workers"])
        args.random_seed = int(search["seed"])
        args.randomize_search = bool(search["randomize_search"])
        args.objective_upper_bound = int(search["objective_upper_bound"])
        args.memory_limit_mib = float(search["memory_limit_mib"])
        args.dense_hint = bool(search["dense_hint"])
        args.support_hint = repo_root / search["support_hint"] if search.get("support_hint") else None
        args.cascade_all_mixed_states = bool(search["cascade_all_mixed_states"])
    elif not (args.types and args.manifest and args.manifest_acceptance):
        raise AssertionError("direct mode requires types, input, and acceptance")
    if len(args.event_no_good) != len(args.event_acceptance):
        raise AssertionError("every event no-good needs one acceptance")
    if len(args.rectangle_bundle) != len(args.rectangle_acceptance):
        raise AssertionError("every rectangle bundle needs one acceptance")
    if len(args.symmetry_bundle) != len(args.symmetry_acceptance):
        raise AssertionError("every symmetry bundle needs one acceptance")
    if len(args.pairing_audit) != len(args.pairing_acceptance):
        raise AssertionError("every pairing audit needs one acceptance")
    if len(args.pairing_symmetry_bundle) != len(args.pairing_symmetry_acceptance):
        raise AssertionError("every pairing symmetry bundle needs one acceptance")
    types = json.loads(args.types.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    acceptance = json.loads(args.manifest_acceptance.read_text(encoding="utf-8"))
    types_sha = hashlib.sha256(args.types.read_bytes()).hexdigest()
    manifest_sha = hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    if not acceptance.get("accepted"):
        raise AssertionError("schema manifest is not independently accepted")
    if acceptance["types_sha256"] != types_sha or acceptance["manifest_sha256"] != manifest_sha:
        raise AssertionError("manifest acceptance identity mismatch")
    type_row = next(row for row in types["types"] if row["type_index"] == manifest["type_index"])
    triple = tuple(tuple(tuple(edge) for edge in matching) for matching in type_row["canonical_triple"])
    pure_owner = {edge: owner for owner, matching in enumerate(triple) for edge in matching}
    pure_edges = set(pure_owner)
    fourths = tuple(matching for matching in ALL_MATCHINGS if not (set(matching) & pure_edges))
    fourth = fourths[manifest["fourth_index"]]
    fourth_edges = set(fourth)
    graph_matchings = tuple(matching for matching in ALL_MATCHINGS if set(matching) <= pure_edges | fourth_edges)
    declared_matchings = tuple(tuple(tuple(edge) for edge in matching) for matching in manifest["matching_catalogue"])
    if declared_matchings != graph_matchings:
        raise AssertionError("manifest matching catalogue mismatch")

    schema_started = time.perf_counter()
    ratio_records = defaultdict(list)
    for state in range(3 ** N):
        colours = decode(state)
        if len(set(colours)) == 1:
            continue
        monomials = [
            tuple((edge, colours[edge[0]], colours[edge[1]]) for edge in matching)
            for matching in graph_matchings
        ]
        for left, right in itertools.combinations(range(len(graph_matchings)), 2):
            ratio_records[ratio_key(monomials[left], monomials[right])].append((state, left, right))
    retained = {
        compact(serialise_ratio(ratio)): (ratio, records)
        for ratio, records in ratio_records.items()
        if len({state for state, _, _ in records}) >= 2
    }
    declared = {compact(item["ratio"]): item for item in manifest["retained_classes"]}
    if set(retained) != set(declared):
        raise AssertionError("recomputed retained ratio classes differ from manifest")
    for key, (_, records) in retained.items():
        item = declared[key]
        if item["record_count"] != len(records):
            raise AssertionError("manifest record count mismatch")
        if item["state_count"] != len({state for state, _, _ in records}):
            raise AssertionError("manifest state count mismatch")
        if item["records_sha256"] != hashlib.sha256(compact(sorted(records))).hexdigest():
            raise AssertionError("manifest record digest mismatch")
    schema_seconds = time.perf_counter() - schema_started
    peak_observed_mib = check_memory(args.memory_limit_mib, "schema reconstruction")

    build_started = time.perf_counter()
    model = cp_model.CpModel()
    pure_extra = {
        (edge, left, right): model.NewBoolVar(f"p_{edge[0]}_{edge[1]}_{left}_{right}")
        for edge, owner in pure_owner.items() for left in range(3) for right in range(3)
        if (left, right) != (owner, owner)
    }
    fourth_support = {
        (edge, left, right): model.NewBoolVar(f"f_{edge[0]}_{edge[1]}_{left}_{right}")
        for edge in fourth for left in range(3) for right in range(3)
    }
    for edge in fourth:
        model.Add(sum(fourth_support[edge, left, right] for left in range(3) for right in range(3)) >= 1)
    if args.dense_hint:
        for variable in pure_extra.values():
            model.AddHint(variable, 1)
        for variable in fourth_support.values():
            model.AddHint(variable, 1)
    if args.support_hint:
        hint_source = json.loads(args.support_hint.read_text(encoding="utf-8"))
        if hint_source["types_sha256"] != types_sha or hint_source["manifest_sha256"] != manifest_sha:
            raise AssertionError("support hint identity mismatch")
        hinted_pure = {(tuple(item[0]), item[1], item[2]) for item in hint_source["active_pure_extras"]}
        hinted_fourth = {(tuple(item[0]), item[1], item[2]) for item in hint_source["active_fourth_entries"]}
        for entry, variable in pure_extra.items():
            model.AddHint(variable, int(entry in hinted_pure))
        for entry, variable in fourth_support.items():
            model.AddHint(variable, int(entry in hinted_fourth))
    if args.fix_dense_support:
        for variable in pure_extra.values():
            model.Add(variable == 1)
        for variable in fourth_support.values():
            model.Add(variable == 1)
    fixed_support_sha = None
    if args.fixed_support:
        fixed_source = json.loads(args.fixed_support.read_text(encoding="utf-8"))
        if fixed_source["types_sha256"] != types_sha or fixed_source["type_index"] != manifest["type_index"]:
            raise AssertionError("fixed support identity mismatch")
        fixed_pure = {(tuple(item[0]), item[1], item[2]) for item in fixed_source["active_pure_extras"]}
        fixed_fourth = {(tuple(item[0]), item[1], item[2]) for item in fixed_source["active_fourth_entries"]}
        for entry, variable in pure_extra.items():
            model.Add(variable == int(entry in fixed_pure))
        for entry, variable in fourth_support.items():
            model.Add(variable == int(entry in fixed_fourth))
        fixed_support_sha = hashlib.sha256(args.fixed_support.read_bytes()).hexdigest()

    row_terms = {}
    row_fixed = {}
    binomial_indicator = {}
    trinomial_indicator = {}
    five_term_indicator = {}
    seven_term_indicator = {}
    four_term_indicator = {}
    uniform_terms = {}
    uniform_binomial_indicator = {}
    term_variables = 0
    singleton_constraints = 0
    for state in range(3 ** N):
        colours = decode(state)
        if len(set(colours)) == 1:
            continue
        terms = []
        variable_terms = []
        fixed_count = 0
        for matching_index, matching in enumerate(graph_matchings):
            variables = []
            for edge in matching:
                entry = (edge, colours[edge[0]], colours[edge[1]])
                if edge in fourth_edges:
                    variables.append(fourth_support[entry])
                else:
                    owner = pure_owner[edge]
                    if (colours[edge[0]], colours[edge[1]]) != (owner, owner):
                        variables.append(pure_extra[entry])
            if not variables:
                fixed_count += 1
                terms.append(None)
                continue
            term = model.NewBoolVar(f"t_{state}_{matching_index}")
            for variable in variables:
                model.Add(term <= variable)
            model.Add(term >= sum(variables) - len(variables) + 1)
            terms.append(term)
            variable_terms.append(term)
            term_variables += 1
            if args.dense_hint:
                model.AddHint(term, 1)
        if fixed_count == 0:
            model.Add(sum(variable_terms) != 1)
            singleton_constraints += 1
        elif fixed_count == 1:
            model.AddBoolOr(variable_terms)
            singleton_constraints += 1
        row_terms[state] = terms
        row_fixed[state] = fixed_count
        binomial_indicator[state] = add_exact_cardinality_indicator(
            model, variable_terms, fixed_count, 2, f"b_{state}"
        )
        trinomial_indicator[state] = add_exact_cardinality_indicator(
            model, variable_terms, fixed_count, 3, f"q_{state}"
        )
        four_term_indicator[state] = add_exact_cardinality_indicator(
            model, variable_terms, fixed_count, 4, f"r4_{state}"
        )
        five_term_indicator[state] = add_exact_cardinality_indicator(
            model, variable_terms, fixed_count, 5, f"r5_{state}"
        )
        seven_term_indicator[state] = add_exact_cardinality_indicator(
            model, variable_terms, fixed_count, 7, f"r7_{state}"
        )
        if args.dense_hint:
            model.AddHint(binomial_indicator[state], 0)
            model.AddHint(trinomial_indicator[state], 0)
            model.AddHint(four_term_indicator[state], 0)
            model.AddHint(five_term_indicator[state], 0)
            model.AddHint(seven_term_indicator[state], 0)
        if state % 256 == 0:
            peak_observed_mib = max(peak_observed_mib, check_memory(args.memory_limit_mib, "row model build"))

    base = sum(3 ** position for position in range(N))
    for colour in range(3):
        state = colour * base
        colours = decode(state)
        terms = []
        variable_terms = []
        fixed_count = 0
        for matching_index, matching in enumerate(graph_matchings):
            variables = []
            for edge in matching:
                entry = (edge, colours[edge[0]], colours[edge[1]])
                if edge in fourth_edges:
                    variables.append(fourth_support[entry])
                else:
                    owner = pure_owner[edge]
                    if (colour, colour) != (owner, owner):
                        variables.append(pure_extra[entry])
            if not variables:
                fixed_count += 1
                terms.append(None)
                continue
            term = model.NewBoolVar(f"u_{colour}_{matching_index}")
            for variable in variables:
                model.Add(term <= variable)
            model.Add(term >= sum(variables) - len(variables) + 1)
            terms.append(term)
            variable_terms.append(term)
            term_variables += 1
            if args.dense_hint:
                model.AddHint(term, 1)
        uniform_terms[state] = terms
        uniform_binomial_indicator[state] = add_exact_cardinality_indicator(
            model, variable_terms, fixed_count, 2, f"ub_{colour}"
        )
        if args.dense_hint:
            model.AddHint(uniform_binomial_indicator[state], 0)

    group_variables = 0
    pair_implications = 0
    group_conflicts = 0
    five_term_pairing_conflicts = 0
    seven_term_pairing_conflicts = 0
    ratio_state_pairs = defaultdict(lambda: defaultdict(list))
    retained_group_variables = {}
    retained_quotient_group_variables = {}
    retained_index_by_key = {key: index for index, key in enumerate(sorted(retained))}
    for ratio_index, key in enumerate(sorted(retained)):
        _, records = retained[key]
        b_group = model.NewBoolVar(f"B_{ratio_index}")
        q_group = model.NewBoolVar(f"Q_{ratio_index}")
        if args.dense_hint:
            model.AddHint(b_group, 0)
            model.AddHint(q_group, 0)
        group_variables += 2
        retained_group_variables[ratio_index] = b_group
        retained_quotient_group_variables[ratio_index] = q_group
        state_pairs = defaultdict(list)
        for state, left, right in records:
            state_pairs[state].append((left, right))
            ratio_state_pairs[state][ratio_index].append((left, right))
            left_term = row_terms[state][left]
            right_term = row_terms[state][right]
            add_pair_to_group_implication(
                model, binomial_indicator[state], left_term, right_term, b_group
            )
            add_pair_to_group_implication(
                model, trinomial_indicator[state], left_term, right_term, q_group
            )
            pair_implications += 2
        add_group_conflict(model, b_group, q_group)
        group_conflicts += 1
        for state, pairs in state_pairs.items():
            for first, second in itertools.combinations(pairs, 2):
                endpoints = set(first + second)
                if len(endpoints) != 4:
                    raise AssertionError("same-ratio target pairs are not disjoint")
                literals = [b_group.Not(), five_term_indicator[state].Not()]
                for matching_index in sorted(endpoints):
                    term = row_terms[state][matching_index]
                    if term is not None:
                        literals.append(term.Not())
                model.AddBoolOr(literals)
                five_term_pairing_conflicts += 1
            if len(pairs) == 3:
                endpoints = {matching_index for pair in pairs for matching_index in pair}
                if len(endpoints) != 6:
                    raise AssertionError("three same-ratio target pairs are not disjoint")
                literals = [b_group.Not(), seven_term_indicator[state].Not()]
                for matching_index in sorted(endpoints):
                    term = row_terms[state][matching_index]
                    if term is not None:
                        literals.append(term.Not())
                model.AddBoolOr(literals)
                seven_term_pairing_conflicts += 1
        if ratio_index % 256 == 0:
            peak_observed_mib = max(peak_observed_mib, check_memory(args.memory_limit_mib, "ratio model build"))

    pairing_audit_hashes = []
    generalized_pairing_no_goods = 0
    seen_pairing_no_goods = set()
    for audit_path, audit_acceptance_path in zip(args.pairing_audit, args.pairing_acceptance):
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        audit_acceptance = json.loads(audit_acceptance_path.read_text(encoding="utf-8"))
        audit_sha = hashlib.sha256(audit_path.read_bytes()).hexdigest()
        if not audit_acceptance.get("accepted") or audit_acceptance.get("audit_sha256") != audit_sha:
            raise AssertionError("pairing audit is not independently accepted")
        if audit["types_sha256"] != types_sha or audit["type_index"] != manifest["type_index"] or audit["fourth_index"] != manifest["fourth_index"]:
            raise AssertionError("pairing audit identity mismatch")
        if audit_acceptance.get("support_sha256") != audit.get("support_sha256"):
            raise AssertionError("pairing audit support identity mismatch")
        for witness in audit["witnesses"]:
            state = int(witness["target_state"])
            target_indices = tuple(map(int, witness["target_matching_indices"]))
            colours = decode(state)
            monomials = [
                tuple((edge, colours[edge[0]], colours[edge[1]]) for edge in matching)
                for matching in graph_matchings
            ]
            ratio_indices = []
            for pair in witness["paired_positions"]:
                left_position, right_position = map(int, pair)
                left_index = target_indices[left_position]
                right_index = target_indices[right_position]
                key = compact(serialise_ratio(ratio_key(monomials[left_index], monomials[right_index])))
                if key not in retained_index_by_key:
                    raise AssertionError("pairing witness ratio is absent from retained schema")
                ratio_indices.append(retained_index_by_key[key])
            no_good_key = (state, target_indices, tuple(sorted(set(ratio_indices))))
            if no_good_key in seen_pairing_no_goods:
                continue
            seen_pairing_no_goods.add(no_good_key)
            literals = [retained_group_variables[index].Not() for index in no_good_key[2]]
            desired = set(target_indices)
            possible = True
            for matching_index, term in enumerate(row_terms[state]):
                if matching_index in desired:
                    if term is not None:
                        literals.append(term.Not())
                elif term is None:
                    possible = False
                    break
                else:
                    literals.append(term)
            if possible:
                model.AddBoolOr(literals)
                generalized_pairing_no_goods += 1
        pairing_audit_hashes.append(audit_sha)

    pairing_symmetry_hashes = []
    pairing_symmetry_no_goods = 0
    for bundle_path, bundle_acceptance_path in zip(args.pairing_symmetry_bundle, args.pairing_symmetry_acceptance):
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        bundle_acceptance = json.loads(bundle_acceptance_path.read_text(encoding="utf-8"))
        bundle_sha = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
        if not bundle_acceptance.get("accepted") or bundle_acceptance.get("bundle_sha256") != bundle_sha:
            raise AssertionError("pairing symmetry bundle is not independently accepted")
        if (bundle["types_sha256"] != types_sha or bundle["manifest_sha256"] != manifest_sha
                or bundle["type_index"] != manifest["type_index"]
                or bundle["fourth_index"] != manifest["fourth_index"]):
            raise AssertionError("pairing symmetry bundle identity mismatch")
        for event in bundle["events"]:
            state = int(event["target_state"])
            target_indices = tuple(map(int, event["target_matching_indices"]))
            colours = decode(state)
            monomials = [
                tuple((edge, colours[edge[0]], colours[edge[1]]) for edge in matching)
                for matching in graph_matchings
            ]
            ratio_indices = []
            for pair in event["paired_positions"]:
                left_position, right_position = map(int, pair)
                left_index = target_indices[left_position]
                right_index = target_indices[right_position]
                key = compact(serialise_ratio(ratio_key(monomials[left_index], monomials[right_index])))
                if key not in retained_index_by_key:
                    raise AssertionError("pairing symmetry ratio is absent from retained schema")
                ratio_indices.append(retained_index_by_key[key])
            no_good_key = (state, target_indices, tuple(sorted(set(ratio_indices))))
            if no_good_key in seen_pairing_no_goods:
                continue
            seen_pairing_no_goods.add(no_good_key)
            literals = [retained_group_variables[index].Not() for index in no_good_key[2]]
            desired = set(target_indices)
            possible = True
            for matching_index, term in enumerate(row_terms[state]):
                if matching_index in desired:
                    if term is not None:
                        literals.append(term.Not())
                elif term is None:
                    possible = False
                    break
                else:
                    literals.append(term)
            if possible:
                model.AddBoolOr(literals)
                pairing_symmetry_no_goods += 1
        pairing_symmetry_hashes.append(bundle_sha)

    # In an exact five-term row, let an edge join two active target monomials
    # when their Laurent ratio is realized by an exact binomial row.  Two
    # disjoint edges give direct pair cancellation.  If all edges intersect
    # pairwise but have no common endpoint, they form a triangle, whose three
    # minus-sign relations are inconsistent in characteristic zero.  Hence all
    # realized edges must share one active centre.  The existential centre is
    # a compact complete encoding of every multi-ratio five-term obstruction.
    five_term_star_centres = 0
    five_term_star_implications = 0
    for state, terms in row_terms.items():
        centres = [model.NewBoolVar(f"c5_{state}_{matching_index}") for matching_index in range(len(graph_matchings))]
        five_term_star_centres += len(centres)
        model.Add(sum(centres) == 1).OnlyEnforceIf(five_term_indicator[state])
        model.Add(sum(centres) == 0).OnlyEnforceIf(five_term_indicator[state].Not())
        for matching_index, term in enumerate(terms):
            if term is not None:
                model.Add(centres[matching_index] <= term)
        for ratio_index, pairs in ratio_state_pairs[state].items():
            b_group = retained_group_variables[ratio_index]
            for left, right in pairs:
                clause = [five_term_indicator[state].Not(), b_group.Not(), centres[left], centres[right]]
                if terms[left] is not None:
                    clause.append(terms[left].Not())
                if terms[right] is not None:
                    clause.append(terms[right].Not())
                model.AddBoolOr(clause)
                five_term_star_implications += 1


    uniform_binomial_conflicts = 0
    for colour in range(3):
        state = colour * base
        colours = decode(state)
        monomials = [
            tuple((edge, colours[edge[0]], colours[edge[1]]) for edge in matching)
            for matching in graph_matchings
        ]
        for uniform_left, uniform_right in itertools.combinations(range(len(graph_matchings)), 2):
            records = ratio_records.get(ratio_key(monomials[uniform_left], monomials[uniform_right]), ())
            for mixed_state, mixed_left, mixed_right in records:
                literals = [
                    uniform_binomial_indicator[state].Not(),
                    binomial_indicator[mixed_state].Not(),
                ]
                for term in (
                    uniform_terms[state][uniform_left],
                    uniform_terms[state][uniform_right],
                    row_terms[mixed_state][mixed_left],
                    row_terms[mixed_state][mixed_right],
                ):
                    if term is not None:
                        literals.append(term.Not())
                model.AddBoolOr(literals)
                uniform_binomial_conflicts += 1
    if group_variables != manifest["group_indicator_variables"]:
        raise AssertionError("built group-variable count mismatch")
    if pair_implications != manifest["pair_to_group_implications"]:
        raise AssertionError("built pair-implication count mismatch")
    if group_conflicts != manifest["group_conflicts"]:
        raise AssertionError("built group-conflict count mismatch")

    if args.cascade_all_mixed_states and args.cascade_aggregate_state:
        raise AssertionError("choose explicit cascade states or all mixed states, not both")
    cascade_aggregate_states = (
        sorted(row_terms) if args.cascade_all_mixed_states
        else sorted(set(map(int, args.cascade_aggregate_state)))
    )
    cascade_edge_variables = 0
    cascade_degree_variables = 0
    cascade_product_variables = 0
    for state in cascade_aggregate_states:
        if state not in row_terms:
            raise AssertionError("cascade aggregate state is not a mixed row")
        b_edges = []
        q_edges = []
        edge_endpoints = []
        for ratio_index, pairs in ratio_state_pairs[state].items():
            b_group = retained_group_variables[ratio_index]
            # Q-group variables were created in the same retained-index order.
            # Recover it from the deterministic name lookup retained below.
            q_group = retained_quotient_group_variables[ratio_index]
            for left, right in pairs:
                inputs_b = [four_term_indicator[state], b_group]
                inputs_q = [four_term_indicator[state], q_group]
                if row_terms[state][left] is not None:
                    inputs_b.append(row_terms[state][left])
                    inputs_q.append(row_terms[state][left])
                if row_terms[state][right] is not None:
                    inputs_b.append(row_terms[state][right])
                    inputs_q.append(row_terms[state][right])
                b_edge = model.NewBoolVar(f"cb_{state}_{left}_{right}")
                q_edge = model.NewBoolVar(f"cq_{state}_{left}_{right}")
                for variable in inputs_b:
                    model.Add(b_edge <= variable)
                for variable in inputs_q:
                    model.Add(q_edge <= variable)
                model.Add(b_edge >= sum(inputs_b) - len(inputs_b) + 1)
                model.Add(q_edge >= sum(inputs_q) - len(inputs_q) + 1)
                b_edges.append(b_edge)
                q_edges.append(q_edge)
                edge_endpoints.append((left, right))
                cascade_edge_variables += 2
        b_count = model.NewIntVar(0, 6, f"cbn_{state}")
        q_count = model.NewIntVar(0, 6, f"cqn_{state}")
        model.Add(b_count == sum(b_edges))
        model.Add(q_count == sum(q_edges))
        total_product = model.NewIntVar(0, 36, f"ctp_{state}")
        model.AddMultiplicationEquality(total_product, [b_count, q_count])
        degree_products = []
        for matching_index in range(len(graph_matchings)):
            b_degree = model.NewIntVar(0, 3, f"cbd_{state}_{matching_index}")
            q_degree = model.NewIntVar(0, 3, f"cqd_{state}_{matching_index}")
            model.Add(b_degree == sum(
                variable for variable, endpoints in zip(b_edges, edge_endpoints)
                if matching_index in endpoints
            ))
            model.Add(q_degree == sum(
                variable for variable, endpoints in zip(q_edges, edge_endpoints)
                if matching_index in endpoints
            ))
            product = model.NewIntVar(0, 9, f"cdp_{state}_{matching_index}")
            model.AddMultiplicationEquality(product, [b_degree, q_degree])
            degree_products.append(product)
            cascade_degree_variables += 2
            cascade_product_variables += 1
        model.Add(total_product == sum(degree_products))
        cascade_product_variables += 1

    event_no_good_hashes = []
    event_no_goods = 0
    for event_path, event_acceptance_path in zip(args.event_no_good, args.event_acceptance):
        event = json.loads(event_path.read_text(encoding="utf-8"))
        event_acceptance = json.loads(event_acceptance_path.read_text(encoding="utf-8"))
        event_sha = hashlib.sha256(event_path.read_bytes()).hexdigest()
        if not event_acceptance.get("accepted") or event_acceptance.get("event_sha256") != event_sha:
            raise AssertionError("event no-good is not independently accepted")
        if event["types_sha256"] != types_sha or event["type_index"] != manifest["type_index"] or event["fourth_index"] != manifest["fourth_index"]:
            raise AssertionError("event no-good identity mismatch")
        violation_literals = []
        event_possible = True
        for row in event["rows"]:
            state = int(row["state"])
            desired = set(map(int, row["active_matching_indices"]))
            for matching_index, term in enumerate(row_terms[state]):
                if matching_index in desired:
                    if term is not None:
                        violation_literals.append(term.Not())
                elif term is None:
                    event_possible = False
                    break
                else:
                    violation_literals.append(term)
            if not event_possible:
                break
        if event_possible:
            model.AddBoolOr(violation_literals)
            event_no_goods += 1
        event_no_good_hashes.append(event_sha)
    rectangle_bundle_hashes = []
    rectangle_event_no_goods = 0
    for bundle_path, rectangle_acceptance_path in zip(args.rectangle_bundle, args.rectangle_acceptance):
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        rectangle_acceptance = json.loads(rectangle_acceptance_path.read_text(encoding="utf-8"))
        bundle_sha = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
        if not rectangle_acceptance.get("accepted") or rectangle_acceptance.get("bundle_sha256") != bundle_sha:
            raise AssertionError("rectangle bundle is not independently accepted")
        if bundle["types_sha256"] != types_sha or bundle["type_index"] != manifest["type_index"] or bundle["fourth_index"] != manifest["fourth_index"]:
            raise AssertionError("rectangle bundle identity mismatch")
        for event in bundle["events"]:
            rows = [
                {"state": row["state"], "active_matching_indices": row["active_matching_indices"]}
                for row in event["source_rows"]
            ]
            rows.append({
                "state": event["target_state"],
                "active_matching_indices": event["target_active_matching_indices"],
            })
            violation_literals = []
            event_possible = True
            for row in rows:
                state = int(row["state"])
                desired = set(map(int, row["active_matching_indices"]))
                for matching_index, term in enumerate(row_terms[state]):
                    if matching_index in desired:
                        if term is not None:
                            violation_literals.append(term.Not())
                    elif term is None:
                        event_possible = False
                        break
                    else:
                        violation_literals.append(term)
                if not event_possible:
                    break
            if event_possible:
                model.AddBoolOr(violation_literals)
                rectangle_event_no_goods += 1
        rectangle_bundle_hashes.append(bundle_sha)
    symmetry_bundle_hashes = []
    symmetry_event_no_goods = 0
    for bundle_path, symmetry_acceptance_path in zip(args.symmetry_bundle, args.symmetry_acceptance):
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        symmetry_acceptance = json.loads(symmetry_acceptance_path.read_text(encoding="utf-8"))
        bundle_sha = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
        if not symmetry_acceptance.get("accepted") or symmetry_acceptance.get("bundle_sha256") != bundle_sha:
            raise AssertionError("symmetry bundle is not independently accepted")
        if (bundle["types_sha256"] != types_sha or bundle["manifest_sha256"] != manifest_sha
                or bundle["type_index"] != manifest["type_index"]
                or bundle["fourth_index"] != manifest["fourth_index"]):
            raise AssertionError("symmetry bundle identity mismatch")
        for event in bundle["events"]:
            violation_literals = []
            event_possible = True
            for row in event["rows"]:
                state = int(row["state"])
                desired = set(map(int, row["active_matching_indices"]))
                for matching_index, term in enumerate(row_terms[state]):
                    if matching_index in desired:
                        if term is not None:
                            violation_literals.append(term.Not())
                    elif term is None:
                        event_possible = False
                        break
                    else:
                        violation_literals.append(term)
                if not event_possible:
                    break
            if event_possible:
                model.AddBoolOr(violation_literals)
                symmetry_event_no_goods += 1
        symmetry_bundle_hashes.append(bundle_sha)
    support_cost_expression = 37 * sum(pure_extra.values()) + sum(fourth_support.values())
    if args.objective_upper_bound is not None:
        model.Add(support_cost_expression <= args.objective_upper_bound)
    if not args.fix_dense_support and not args.fixed_support:
        model.Minimize(support_cost_expression)
    build_seconds = time.perf_counter() - build_started
    peak_observed_mib = max(peak_observed_mib, check_memory(args.memory_limit_mib, "completed model"))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = args.seconds
    solver.parameters.num_search_workers = args.workers
    solver.parameters.random_seed = args.random_seed
    solver.parameters.randomize_search = args.randomize_search
    solver.parameters.log_search_progress = False
    solver.parameters.cp_model_presolve = not args.disable_presolve
    solver.parameters.stop_after_first_solution = args.stop_after_first_solution
    if args.memory_limit_mib:
        solver.parameters.max_memory_in_mb = int(args.memory_limit_mib)
    solve_started = time.perf_counter()
    status = solver.Solve(model)
    solve_seconds = time.perf_counter() - solve_started
    payload = {
        "schema": "run-073-result-v1",
        "search_id": args.search_id,
        "evidence_level": "exact necessary support model; positive survivors only",
        "types_sha256": types_sha,
        "manifest_sha256": manifest_sha,
        "manifest_acceptance_sha256": hashlib.sha256(args.manifest_acceptance.read_bytes()).hexdigest(),
        "type_index": manifest["type_index"],
        "graph_type": type_row["graph_type"],
        "triple": type_row["canonical_triple"],
        "fourth_index": manifest["fourth_index"],
        "fourth_matching": [list(edge) for edge in fourth],
        "graph_perfect_matchings": len(graph_matchings),
        "pure_extra_variables": len(pure_extra),
        "fourth_variables": len(fourth_support),
        "term_variables": term_variables,
        "cardinality_indicators": 5 * len(row_terms) + len(uniform_binomial_indicator),
        "singleton_constraints": singleton_constraints,
        "group_indicator_variables": group_variables,
        "pair_to_group_implications": pair_implications,
        "group_conflicts": group_conflicts,
        "five_term_pairing_conflicts": five_term_pairing_conflicts,
        "seven_term_pairing_conflicts": seven_term_pairing_conflicts,
        "pairing_audit_sha256": pairing_audit_hashes,
        "generalized_pairing_no_goods": generalized_pairing_no_goods,
        "pairing_symmetry_bundle_sha256": pairing_symmetry_hashes,
        "pairing_symmetry_no_goods": pairing_symmetry_no_goods,
        "five_term_star_centres": five_term_star_centres,
        "five_term_star_implications": five_term_star_implications,
        "cascade_aggregate_states": cascade_aggregate_states,
        "cascade_all_mixed_states": args.cascade_all_mixed_states,
        "cascade_edge_variables": cascade_edge_variables,
        "cascade_degree_variables": cascade_degree_variables,
        "cascade_product_variables": cascade_product_variables,
        "uniform_binomial_conflicts": uniform_binomial_conflicts,
        "memory_limit_mib": args.memory_limit_mib,
        "peak_observed_working_set_mib": peak_observed_mib,
        "dense_hint": args.dense_hint,
        "support_hint_sha256": hashlib.sha256(args.support_hint.read_bytes()).hexdigest() if args.support_hint else None,
        "fix_dense_support": args.fix_dense_support,
        "fixed_support_sha256": fixed_support_sha,
        "event_no_good_sha256": event_no_good_hashes,
        "event_no_goods": event_no_goods,
        "rectangle_bundle_sha256": rectangle_bundle_hashes,
        "rectangle_event_no_goods": rectangle_event_no_goods,
        "symmetry_bundle_sha256": symmetry_bundle_hashes,
        "symmetry_event_no_goods": symmetry_event_no_goods,
        "disable_presolve": args.disable_presolve,
        "random_seed": args.random_seed,
        "randomize_search": args.randomize_search,
        "objective_upper_bound": args.objective_upper_bound,
        "stop_after_first_solution": args.stop_after_first_solution,
        "schema_seconds": schema_seconds,
        "model_build_seconds": build_seconds,
        "solver_status": solver.StatusName(status),
        "solve_seconds": solve_seconds,
        "solver_wall_seconds": solver.WallTime(),
        "best_objective_bound": solver.BestObjectiveBound(),
        "branches": solver.NumBranches(),
        "conflicts": solver.NumConflicts(),
    }
    if status in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        active_pure = [entry for entry, variable in pure_extra.items() if solver.Value(variable)]
        active_fourth = [entry for entry, variable in fourth_support.items() if solver.Value(variable)]
        payload["pure_extra_count"] = len(active_pure)
        payload["fourth_entry_count"] = len(active_fourth)
        payload["support_cost"] = 37 * len(active_pure) + len(active_fourth)
        payload["active_pure_extras"] = [[list(edge), left, right] for edge, left, right in active_pure]
        payload["active_fourth_entries"] = [[list(edge), left, right] for edge, left, right in active_fourth]
        if not args.fix_dense_support and not args.fixed_support:
            payload["objective"] = int(round(solver.ObjectiveValue()))
    payload["canonical_outcome_sha256"] = hashlib.sha256(canonical(payload)).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = args.output.with_name(args.output.name + ".tmp")
    temporary_output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    temporary_output.replace(args.output)
    print(json.dumps({key: value for key, value in payload.items() if key not in {
        "active_pure_extras", "active_fourth_entries", "triple"
    }}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
