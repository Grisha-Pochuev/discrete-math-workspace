#!/usr/bin/env python3
"""Neutral bounded exact-event residue search and strict collector."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import platform
import random
import shutil
import sys
import time


HERE = Path(__file__).resolve().parent
LOCAL_RUNTIME = Path(__file__).resolve().parents[2] / ".local-tools" / "ortools-runtime2"
if LOCAL_RUNTIME.is_dir():
    sys.path.insert(0, str(LOCAL_RUNTIME))
VERTICES = tuple(range(8))
COLOURS = (0, 1, 2)


def edge_key(u, v, a, b):
    return (u, v, a, b) if u < v else (v, u, b, a)


MANDATORY = frozenset({
    edge_key(1, 4, 0, 0), edge_key(2, 5, 0, 0),
    edge_key(0, 2, 1, 1), edge_key(3, 4, 1, 1),
    edge_key(0, 5, 2, 2), edge_key(1, 3, 2, 2),
    edge_key(0, 6, 0, 0), edge_key(3, 7, 0, 0),
    edge_key(1, 6, 1, 1), edge_key(5, 7, 1, 1),
    edge_key(2, 6, 2, 2), edge_key(4, 7, 2, 2),
})
GRAPH_EDGES = frozenset((u, v) for u, v, _a, _b in MANDATORY)
ENTRY_KEYS = tuple(
    edge_key(u, v, a, b)
    for u, v in sorted(GRAPH_EDGES)
    for a in COLOURS for b in COLOURS
)
ENTRY_SET = frozenset(ENTRY_KEYS)
EXTRAS = tuple(item for item in ENTRY_KEYS if item not in MANDATORY)


def perfect_matchings(vertices):
    vertices = tuple(vertices)
    if not vertices:
        yield ()
        return
    first = vertices[0]
    for position, partner in enumerate(vertices[1:], start=1):
        rest = vertices[1:position] + vertices[position + 1:]
        for tail in perfect_matchings(rest):
            yield ((first, partner),) + tail


GRAPH_MATCHINGS = tuple(
    matching for matching in perfect_matchings(VERTICES)
    if all((u, v) in GRAPH_EDGES for u, v in matching)
)
COLOURINGS = tuple(itertools.product(COLOURS, repeat=8))
COLOURING_NAMES = tuple("".join(map(str, item)) for item in COLOURINGS)


def canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def seal(payload):
    result = dict(payload)
    result.pop("canonical_sha256", None)
    result["canonical_sha256"] = hashlib.sha256(canonical_bytes(result)).hexdigest()
    return result


def check_seal(payload):
    copy = dict(payload)
    claimed = copy.pop("canonical_sha256", None)
    if not claimed or hashlib.sha256(canonical_bytes(copy)).hexdigest() != claimed:
        raise ValueError("canonical payload mismatch")
    return claimed


def atomic_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    temporary.replace(path)


def write_gzip(path, payload):
    path = Path(path)
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as stream:
            stream.write(canonical_bytes(payload))


def load_spec(path):
    path = Path(path)
    spec = json.loads(path.read_text(encoding="utf-8"))
    expected = [
        {"id": f"s{group * 4 + slot:03d}", "group": group, "slot": slot,
         "seed": spec.get("seed_base", 0) + (group * 4 + slot) * spec.get("seed_stride", 0)}
        for group in range(spec.get("physical_jobs", 0))
        for slot in range(spec.get("logical_workers_per_job", 0))
    ]
    if (
        spec.get("schema") != "neutral-event-residue-spec-v1"
        or spec.get("run_id") != "run-078"
        or spec.get("physical_jobs") != 19
        or spec.get("logical_workers_per_job") != 4
        or spec.get("max_parallel") != 19
        or spec.get("seed_base") != 78000001
        or spec.get("seed_stride") != 7919
        or spec.get("entry_count") != len(ENTRY_KEYS)
        or spec.get("optional_entry_count") != len(EXTRAS)
        or spec.get("matching_count") != len(GRAPH_MATCHINGS)
        or spec.get("script_sha256") != sha256_file(__file__)
    ):
        raise ValueError("immutable specification mismatch")
    spec["searches"] = expected
    return spec


def active_data(support):
    ordered = tuple(sorted(support))
    index = {entry: position for position, entry in enumerate(ordered)}
    rows = {}
    for colouring, name in zip(COLOURINGS, COLOURING_NAMES):
        terms = []
        for matching_index, matching in enumerate(GRAPH_MATCHINGS):
            exponent = [0] * len(ordered)
            for u, v in matching:
                entry = (u, v, colouring[u], colouring[v])
                if entry not in index:
                    break
                exponent[index[entry]] += 1
            else:
                terms.append((matching_index, tuple(exponent)))
        rows[name] = terms
    return ordered, rows


def pair_connected(support, pair):
    adjacency = {vertex: set() for vertex in VERTICES}
    for u, v in GRAPH_EDGES:
        if any((u, v, a, b) in support for a in pair for b in pair):
            adjacency[u].add(v)
            adjacency[v].add(u)
    seen = {0}
    stack = [0]
    while stack:
        vertex = stack.pop()
        for neighbour in adjacency[vertex] - seen:
            seen.add(neighbour)
            stack.append(neighbour)
    return len(seen) == len(VERTICES)


def has_cut_witness(support):
    for u, v in ((1, 6), (5, 7)):
        for rows in itertools.combinations(COLOURS, 2):
            for columns in itertools.combinations(COLOURS, 2):
                for permutation in ((0, 1), (1, 0)):
                    if all(
                        (u, v, rows[index], columns[permutation[index]]) in support
                        for index in range(2)
                    ):
                        return True
    return False


def validate_support(support):
    support = frozenset(tuple(item) for item in support)
    if not MANDATORY <= support or not support <= ENTRY_SET:
        raise ValueError("support coverage mismatch")
    if any(not pair_connected(support, pair) for pair in itertools.combinations(COLOURS, 2)):
        raise ValueError("pair connectivity mismatch")
    if not has_cut_witness(support):
        raise ValueError("cut witness mismatch")
    _ordered, rows = active_data(support)
    for name, terms in rows.items():
        if len(set(name)) == 1:
            if not terms:
                raise ValueError("missing retained row")
        elif len(terms) == 1:
            raise ValueError("forbidden singleton row")
    return support


def lattice_solver(relations, variable_count):
    from sympy import ZZ
    from sympy.polys.matrices import DomainMatrix
    from sympy.polys.matrices.normalforms import smith_normal_decomp

    matrix = DomainMatrix.from_list_sympy(
        variable_count, len(relations), list(map(list, zip(*relations)))
    ).convert_to(ZZ)
    diagonal, left, right = smith_normal_decomp(matrix)
    rank = sum(bool(diagonal[i, i].element) for i in range(min(diagonal.shape)))
    right_matrix = right.to_Matrix()
    for column in range(rank, len(relations)):
        coefficients = [int(right_matrix[row, column]) for row in range(len(relations))]
        if sum(coefficients) % 2:
            return diagonal, left, right_matrix, rank, coefficients
    return diagonal, left, right_matrix, rank, None


def solve_relation(lattice, difference, relation_count, variable_count):
    from sympy import Matrix, ZZ
    from sympy.polys.matrices import DomainMatrix

    diagonal, left, right, rank, _kernel = lattice
    column = DomainMatrix.from_list_sympy(
        variable_count, 1, [[value] for value in difference]
    ).convert_to(ZZ)
    transformed = left * column
    if any(transformed[index, 0].element for index in range(rank, variable_count)):
        return None
    coordinates = [0] * relation_count
    for index in range(rank):
        divisor = int(diagonal[index, index].element)
        value = int(transformed[index, 0].element)
        if value % divisor:
            return None
        coordinates[index] = value // divisor
    return [int(value) for value in right * Matrix(coordinates)]


def exact_audit(support):
    from sympy import Matrix, ZZ
    from sympy.polys.matrices import DomainMatrix

    ordered, rows = active_data(support)
    variable_count = len(ordered)
    names = []
    relations = []
    for name, terms in rows.items():
        if len(set(name)) == 1 or len(terms) != 2:
            continue
        names.append(name)
        relations.append([a - b for a, b in zip(terms[0][1], terms[1][1])])
    if not relations:
        return {"status": "ALGEBRA_FRONTIER", "reason": "NO_BINOMIAL_RELATIONS"}
    lattice = lattice_solver(relations, variable_count)
    diagonal, left, right, rank, kernel = lattice
    if kernel is not None:
        used = [index for index, coefficient in enumerate(kernel) if coefficient]
        return {
            "status": "REFUTED_SIGN_KERNEL",
            "event": {
                "kind": "mixed_sign_kernel",
                "patterns": {names[index]: [term[0] for term in rows[names[index]]] for index in used},
                "relation_combination": [
                    {"mixed_colouring": names[index], "coefficient": kernel[index]}
                    for index in used
                ],
            },
        }

    for target_name in ("00000000", "11111111", "22222222"):
        target_terms = rows[target_name]
        groups = defaultdict(lambda: {1: [], -1: []})
        for matching_index, exponent in target_terms:
            column = DomainMatrix.from_list_sympy(
                variable_count, 1, [[value] for value in exponent]
            ).convert_to(ZZ)
            transformed = left * column
            coordinates = [0] * len(relations)
            quotient = []
            for index in range(rank):
                divisor = abs(int(diagonal[index, index].element))
                value = int(transformed[index, 0].element)
                remainder = value % divisor
                quotient.append(remainder)
                coordinates[index] = (
                    value - remainder
                ) // int(diagonal[index, index].element)
            quotient.extend(
                int(transformed[index, 0].element)
                for index in range(rank, variable_count)
            )
            coefficients = [int(value) for value in right * Matrix(coordinates)]
            sign = -1 if sum(coefficients) % 2 else 1
            groups[tuple(quotient)][sign].append((matching_index, exponent))
        if target_terms and all(
            len(bucket[1]) == len(bucket[-1]) for bucket in groups.values()
        ):
            pairs = []
            used_relations = set()
            for bucket in groups.values():
                for positive, negative in zip(bucket[1], bucket[-1]):
                    difference = [
                        a - b for a, b in zip(positive[1], negative[1])
                    ]
                    coefficients = solve_relation(
                        lattice, difference, len(relations), variable_count
                    )
                    if coefficients is None or sum(coefficients) % 2 != 1:
                        raise ValueError("target pairing export failed")
                    used = [index for index, value in enumerate(coefficients) if value]
                    used_relations.update(used)
                    pairs.append({
                        "positive_target_matching": positive[0],
                        "negative_target_matching": negative[0],
                        "relation_combination": [
                            {"mixed_colouring": names[index], "coefficient": coefficients[index]}
                            for index in used
                        ],
                    })
            patterns = {target_name: [term[0] for term in target_terms]}
            for index in sorted(used_relations):
                patterns[names[index]] = [term[0] for term in rows[names[index]]]
            return {
                "status": "REFUTED_TARGET_ZERO",
                "event": {
                    "kind": "target_zero",
                    "target_colouring": target_name,
                    "patterns": patterns,
                    "pair_certificates": pairs,
                },
            }
    return {
        "status": "ALGEBRA_FRONTIER",
        "reason": "NO_EXPORTED_EXACT_OBSTRUCTION",
        "binomial_rows": len(relations),
        "lattice_rank": rank,
        "target_term_counts": {
            name: len(rows[name]) for name in ("00000000", "11111111", "22222222")
        },
    }


def row_monomials(support, colouring_text):
    colouring = tuple(map(int, colouring_text))
    ordered = tuple(sorted(support))
    index = {entry: position for position, entry in enumerate(ordered)}
    result = []
    for matching_index, matching in enumerate(GRAPH_MATCHINGS):
        exponent = [0] * len(ordered)
        for u, v in matching:
            entry = (u, v, colouring[u], colouring[v])
            if entry not in index:
                break
            exponent[index[entry]] += 1
        else:
            result.append((matching_index, exponent))
    return result


def replay_event(event):
    support = frozenset(tuple(item) for item in event["source_support"])
    if not MANDATORY <= support or not support <= ENTRY_SET:
        raise ValueError("event source support mismatch")
    reconstructed = {}
    for colouring, expected in event["patterns"].items():
        terms = row_monomials(support, colouring)
        if [matching for matching, _exponent in terms] != expected:
            raise ValueError("event pattern mismatch")
        reconstructed[colouring] = terms
    if event["kind"] == "target_zero":
        target = {
            matching: exponent
            for matching, exponent in reconstructed[event["target_colouring"]]
        }
        for pair in event["pair_certificates"]:
            difference = [
                a - b for a, b in zip(
                    target[pair["positive_target_matching"]],
                    target[pair["negative_target_matching"]],
                )
            ]
            total = [0] * len(support)
            parity = 0
            for record in pair["relation_combination"]:
                row = reconstructed[record["mixed_colouring"]]
                if len(row) != 2:
                    raise ValueError("claimed row is not binomial")
                relation = [a - b for a, b in zip(row[0][1], row[1][1])]
                coefficient = record["coefficient"]
                total = [a + coefficient * b for a, b in zip(total, relation)]
                parity += coefficient
            if total != difference or parity % 2 != 1:
                raise ValueError("target-zero replay failed")
    elif event["kind"] == "mixed_sign_kernel":
        total = [0] * len(support)
        parity = 0
        for record in event["relation_combination"]:
            row = reconstructed[record["mixed_colouring"]]
            if len(row) != 2:
                raise ValueError("claimed row is not binomial")
            relation = [a - b for a, b in zip(row[0][1], row[1][1])]
            coefficient = record["coefficient"]
            total = [a + coefficient * b for a, b in zip(total, relation)]
            parity += coefficient
        if any(total) or parity % 2 != 1:
            raise ValueError("sign-kernel replay failed")
    else:
        raise ValueError("unknown event kind")


def build_model(seed):
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    entries = {
        entry: model.new_bool_var("e_" + "_".join(map(str, entry)))
        for entry in ENTRY_KEYS
    }
    for entry in MANDATORY:
        model.add(entries[entry] == 1)
    for pair in itertools.combinations(COLOURS, 2):
        for mask in range(1, 1 << 7):
            crossing = []
            for u, v in GRAPH_EDGES:
                if ((mask >> u) & 1) == ((mask >> v) & 1):
                    continue
                crossing.extend(entries[(u, v, a, b)] for a in pair for b in pair)
            model.add_bool_or(crossing)
    cut_witnesses = []
    for u, v in ((1, 6), (5, 7)):
        for rows in itertools.combinations(COLOURS, 2):
            for columns in itertools.combinations(COLOURS, 2):
                for permutation in ((0, 1), (1, 0)):
                    selected = [
                        entries[(u, v, rows[index], columns[permutation[index]])]
                        for index in range(2)
                    ]
                    witness = model.new_bool_var(f"w_{len(cut_witnesses)}")
                    for variable in selected:
                        model.add(witness <= variable)
                    model.add(witness >= sum(selected) - 1)
                    cut_witnesses.append(witness)
    model.add_bool_or(cut_witnesses)
    term_variables = {}
    for colouring, name in zip(COLOURINGS, COLOURING_NAMES):
        terms = []
        for matching_index, matching in enumerate(GRAPH_MATCHINGS):
            used = [entries[(u, v, colouring[u], colouring[v])] for u, v in matching]
            term = model.new_bool_var(f"t_{name}_{matching_index}")
            for variable in used:
                model.add(term <= variable)
            model.add(term >= sum(used) - (len(used) - 1))
            term_variables[(name, matching_index)] = term
            terms.append(term)
        if len(set(colouring)) == 1:
            model.add(sum(terms) >= 1)
        else:
            model.add(sum(terms) != 1)
    generator = random.Random(seed)
    tie = {entry: generator.randrange(1, 998) for entry in EXTRAS}
    model.minimize(
        100000 * sum(entries[entry] for entry in EXTRAS)
        + sum(tie[entry] * entries[entry] for entry in EXTRAS)
    )
    return model, entries, term_variables


def result_payload(spec, spec_path, search, status, started, events, iterations, frontier):
    return seal({
        "schema": "neutral-event-residue-result-v1",
        "search": search,
        "status": status,
        "elapsed_seconds": time.monotonic() - started,
        "workers": 1,
        "event_count": len(events),
        "events": events,
        "iterations": iterations,
        "algebra_frontier": frontier,
        "spec_sha256": sha256_file(spec_path),
        "script_sha256": spec["script_sha256"],
        "solver": "OR-Tools CP-SAT 9.15.6755",
        "python": platform.python_version(),
        "scope_warning": (
            "Replayed exact events and frontiers are retained; bounded or solver-negative states are diagnostic only."
        ),
    })


def command_worker(args):
    from ortools.sat.python import cp_model

    spec = load_spec(args.spec)
    search = next((item for item in spec["searches"] if item["id"] == args.search_id), None)
    if search is None:
        raise ValueError("unknown search id")
    seconds = min(3.0, spec["seconds_per_search"]) if args.smoke else spec["seconds_per_search"]
    max_events = min(1, spec["max_events"]) if args.smoke else spec["max_events"]
    started = time.monotonic()
    model, entries, term_variables = build_model(search["seed"])
    events = []
    iterations = []
    frontier = None
    status = "RUNNING"
    while len(events) < max_events:
        remaining = seconds - (time.monotonic() - started)
        if remaining <= 0.25:
            status = "BOUNDED_COMPLETE"
            break
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = min(spec["seconds_per_round"], remaining)
        solver.parameters.max_memory_in_mb = spec["memory_mib_per_search"]
        solver.parameters.num_workers = 1
        solver.parameters.random_seed = search["seed"] + len(iterations) * 1009
        solver.parameters.randomize_search = True
        solve_status = solver.solve(model)
        name = solver.status_name(solve_status)
        iteration = {
            "iteration": len(iterations),
            "solver_status": name,
            "solver_seconds": solver.wall_time,
            "conflicts": solver.num_conflicts,
            "branches": solver.num_branches,
        }
        if solve_status == cp_model.INFEASIBLE:
            status = "SOLVER_INFEASIBLE_DIAGNOSTIC"
            iterations.append(iteration)
            break
        if solve_status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            iteration["audit_status"] = "NO_SUPPORT"
            iterations.append(iteration)
            atomic_json(
                args.output,
                result_payload(spec, args.spec, search, "RUNNING", started, events, iterations, frontier),
            )
            continue
        support = frozenset(entry for entry in ENTRY_KEYS if solver.value(entries[entry]))
        audit = exact_audit(support)
        iteration.update({
            "additional_entries": len(support) - len(MANDATORY),
            "best_bound": solver.best_objective_bound,
            "audit_status": audit["status"],
        })
        iterations.append(iteration)
        if audit["status"] == "ALGEBRA_FRONTIER":
            frontier = {
                "support": [list(item) for item in sorted(support)],
                "reason": audit["reason"],
                "binomial_rows": audit.get("binomial_rows"),
                "lattice_rank": audit.get("lattice_rank"),
                "target_term_counts": audit.get("target_term_counts"),
            }
            status = "ALGEBRA_FRONTIER"
            break
        event = audit["event"]
        event["event_id"] = len(events)
        event["source_support"] = [list(item) for item in sorted(support)]
        replay_event(event)
        events.append(event)
        literals = []
        for colouring, active_pattern in event["patterns"].items():
            active_pattern = set(active_pattern)
            for matching_index in range(len(GRAPH_MATCHINGS)):
                variable = term_variables[(colouring, matching_index)]
                literals.append(variable.Not() if matching_index in active_pattern else variable)
        model.add_bool_or(literals)
        atomic_json(
            args.output,
            result_payload(spec, args.spec, search, "RUNNING", started, events, iterations, frontier),
        )
    else:
        status = "EVENT_CAP_COMPLETE"
    atomic_json(
        args.output,
        result_payload(spec, args.spec, search, status, started, events, iterations, frontier),
    )
    print(json.dumps({
        "search": search["id"], "status": status, "events": len(events),
        "iterations": len(iterations), "frontier": frontier is not None,
    }, sort_keys=True))


def validate_result(result, spec, spec_path):
    check_seal(result)
    expected = {item["id"]: item for item in spec["searches"]}
    search = result.get("search", {})
    if (
        result.get("schema") != "neutral-event-residue-result-v1"
        or search.get("id") not in expected
        or search != expected[search["id"]]
        or result.get("status") not in {
            "BOUNDED_COMPLETE", "EVENT_CAP_COMPLETE",
            "SOLVER_INFEASIBLE_DIAGNOSTIC", "ALGEBRA_FRONTIER",
        }
        or result.get("workers") != 1
        or result.get("spec_sha256") != sha256_file(spec_path)
        or result.get("script_sha256") != spec["script_sha256"]
        or result.get("event_count") != len(result.get("events", []))
        or [event.get("event_id") for event in result.get("events", [])]
            != list(range(result.get("event_count", -1)))
    ):
        raise ValueError("result contract mismatch")
    for event in result["events"]:
        replay_event(event)
    frontier = result.get("algebra_frontier")
    if (result["status"] == "ALGEBRA_FRONTIER") != (frontier is not None):
        raise ValueError("frontier status mismatch")
    if frontier is not None:
        support = validate_support(frontier["support"])
        replay = exact_audit(support)
        if replay.get("status") != "ALGEBRA_FRONTIER" or replay.get("reason") != frontier["reason"]:
            raise ValueError("frontier algebra replay mismatch")
    return result


def require_exact_coverage(expected, seen):
    expected = set(expected)
    seen = set(seen)
    missing = sorted(expected - seen)
    unexpected = sorted(seen - expected)
    if missing or unexpected:
        raise ValueError(
            f"search coverage mismatch: missing={missing}, unexpected={unexpected}"
        )


def command_validate_group(args):
    spec = load_spec(args.spec)
    expected = {
        item["id"] for item in spec["searches"] if item["group"] == args.group
    }
    seen = set()
    for path in sorted(args.input_root.rglob("result.json")):
        result = validate_result(json.loads(path.read_text(encoding="utf-8")), spec, args.spec)
        search_id = result["search"]["id"]
        exit_path = path.with_name("worker.exit")
        if not exit_path.is_file() or exit_path.read_text(encoding="ascii").strip() != "0":
            raise ValueError(f"worker process failure: {search_id}")
        if result["search"]["group"] != args.group or search_id in seen:
            raise ValueError("unexpected group result")
        seen.add(search_id)
    require_exact_coverage(expected, seen)
    print(json.dumps({"accepted": True, "group": args.group, "searches": len(seen)}))


def event_key(event):
    return canonical_bytes({"patterns": event["patterns"]})


def command_collect(args):
    spec = load_spec(args.spec)
    expected = {item["id"]: item for item in spec["searches"]}
    seen = set()
    results = []
    unique_events = {}
    unique_frontiers = {}
    for path in sorted(args.input_root.rglob("result.json")):
        result = validate_result(json.loads(path.read_text(encoding="utf-8")), spec, args.spec)
        search_id = result["search"]["id"]
        if search_id in seen:
            raise ValueError(f"duplicate search result: {search_id}")
        seen.add(search_id)
        for event in result["events"]:
            key = hashlib.sha256(event_key(event)).hexdigest()
            if key not in unique_events:
                unique_events[key] = {"event": event, "search_ids": []}
            unique_events[key]["search_ids"].append(search_id)
        if result["algebra_frontier"] is not None:
            frontier = result["algebra_frontier"]
            key = hashlib.sha256(canonical_bytes(frontier["support"])).hexdigest()
            if key not in unique_frontiers:
                unique_frontiers[key] = {"frontier": frontier, "search_ids": []}
            unique_frontiers[key]["search_ids"].append(search_id)
        results.append({key: value for key, value in result.items() if key != "events"})
    require_exact_coverage(expected, seen)
    status_histogram = Counter(item["status"] for item in results)
    event_records = [
        {"event_key_sha256": key, **record}
        for key, record in sorted(unique_events.items())
    ]
    frontier_records = [
        {"support_sha256": key, **record}
        for key, record in sorted(unique_frontiers.items())
    ]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary = seal({
        "schema": "neutral-event-residue-collection-v1",
        "workflow_run": str(args.workflow_run),
        "source_sha": args.source_sha,
        "spec_sha256": sha256_file(args.spec),
        "expected_searches": len(expected),
        "received_searches": len(results),
        "physical_jobs": spec["physical_jobs"],
        "independent_single_thread_workers_per_job": spec["logical_workers_per_job"],
        "status_histogram": dict(sorted(status_histogram.items())),
        "total_replayed_events": sum(item["event_count"] for item in results),
        "unique_replayed_events": len(event_records),
        "unique_algebra_frontiers": len(frontier_records),
        "scientific_status": (
            "algebra_frontier_found" if frontier_records else
            "exact_events_extended" if event_records else "bounded_diagnostic_only"
        ),
        "scope_warning": (
            "Every retained event/frontier was independently replayed; bounded negative states do not close the residue."
        ),
    })
    atomic_json(args.output_dir / "summary.json", summary)
    atomic_json(args.output_dir / "frontiers.json", frontier_records)
    write_gzip(args.output_dir / "events.json.gz", event_records)
    write_gzip(args.output_dir / "result-summaries.json.gz", sorted(results, key=lambda item: item["search"]["id"]))
    shutil.copyfile(args.spec, args.output_dir / "input-spec.json")
    files = [
        args.output_dir / "summary.json", args.output_dir / "frontiers.json",
        args.output_dir / "events.json.gz", args.output_dir / "result-summaries.json.gz",
        args.output_dir / "input-spec.json",
    ]
    (args.output_dir / "checksums.sha256").write_text(
        "".join(f"{sha256_file(path)}  {path.name}\n" for path in files),
        encoding="ascii", newline="\n",
    )
    print(json.dumps({
        "accepted": True, "searches": len(results), "events": len(event_records),
        "frontiers": len(frontier_records), "status": summary["scientific_status"],
    }, sort_keys=True))


def command_self_test(args):
    spec = load_spec(args.spec)
    if len(GRAPH_EDGES) != 12 or len(GRAPH_MATCHINGS) != 5 or len(ENTRY_KEYS) != 108 or len(EXTRAS) != 96:
        raise AssertionError("model census mismatch")
    if len(spec["searches"]) != 76:
        raise AssertionError("search coverage mismatch")
    # Exercise canonical identity and the independent support predicates.
    probe = seal({"schema": "probe", "value": [1, 2, 3]})
    check_seal(probe)
    if pair_connected(MANDATORY, (0, 2)):
        raise AssertionError("connectivity countermodel unexpectedly connected")
    expected = {item["id"] for item in spec["searches"]}
    seen = set()
    for search in spec["searches"]:
        result = seal({
            "schema": "neutral-event-residue-result-v1",
            "search": search,
            "status": "BOUNDED_COMPLETE",
            "elapsed_seconds": 0.0,
            "workers": 1,
            "event_count": 0,
            "events": [],
            "iterations": [],
            "algebra_frontier": None,
            "spec_sha256": sha256_file(args.spec),
            "script_sha256": spec["script_sha256"],
            "solver": "synthetic",
            "python": "synthetic",
            "scope_warning": "synthetic collector contract",
        })
        validate_result(result, spec, args.spec)
        if search["id"] in seen:
            raise AssertionError("duplicate synthetic search")
        seen.add(search["id"])
    require_exact_coverage(expected, seen)
    try:
        require_exact_coverage(expected, seen - {"s075"})
    except ValueError as error:
        if "s075" not in str(error):
            raise
    else:
        raise AssertionError("missing synthetic coverage accepted")
    print(json.dumps({
        "accepted": True, "entries": len(ENTRY_KEYS), "matchings": len(GRAPH_MATCHINGS),
        "searches": len(spec["searches"]), "disconnected_probe_rejected": True,
        "complete_collection_accepted": True, "missing_collection_rejected": True,
    }, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    contract_parser = sub.add_parser("contract")
    contract_parser.add_argument("--spec", type=Path, required=True)
    self_parser = sub.add_parser("self-test")
    self_parser.add_argument("--spec", type=Path, required=True)
    worker = sub.add_parser("worker")
    worker.add_argument("--spec", type=Path, required=True)
    worker.add_argument("--search-id", required=True)
    worker.add_argument("--output", type=Path, required=True)
    worker.add_argument("--smoke", action="store_true")
    group = sub.add_parser("validate-group")
    group.add_argument("--spec", type=Path, required=True)
    group.add_argument("--group", type=int, required=True)
    group.add_argument("--input-root", type=Path, required=True)
    collect = sub.add_parser("collect")
    collect.add_argument("--spec", type=Path, required=True)
    collect.add_argument("--input-root", type=Path, required=True)
    collect.add_argument("--output-dir", type=Path, required=True)
    collect.add_argument("--workflow-run", required=True)
    collect.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    if args.command == "contract":
        spec = load_spec(args.spec)
        print(json.dumps({
            "accepted": True, "run_id": spec["run_id"],
            "searches": len(spec["searches"]), "script_sha256": spec["script_sha256"],
        }, sort_keys=True))
    elif args.command == "self-test":
        command_self_test(args)
    elif args.command == "worker":
        command_worker(args)
    elif args.command == "validate-group":
        command_validate_group(args)
    elif args.command == "collect":
        command_collect(args)


if __name__ == "__main__":
    main()
