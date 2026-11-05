"""Exact four-way support-layer enumerator backed by compiled CP-SAT."""

from __future__ import annotations

import argparse
import itertools
import json
import os
from pathlib import Path
import signal
import sys
import time

from ortools.sat.python import cp_model


RUN_ID = "run-032"
PARTITION_VERSION = "parity2-v1"
VERTICES = tuple(range(8))
FACTORS = (
    ((0, 2), (1, 3), (4, 6), (5, 7)),
    ((0, 4), (1, 5), (2, 6), (3, 7)),
    ((0, 6), (1, 7), (2, 4), (3, 5)),
)
RESIDUAL = (
    (0, 5), (0, 7), (1, 4), (1, 6),
    (2, 5), (2, 7), (3, 4), (3, 6),
)
CYCLE_ORDERS = ((0, 5, 2, 7), (1, 4, 3, 6))
MASK64 = (1 << 64) - 1


def edge(a, b):
    return (a, b) if a < b else (b, a)


def perfect_matchings(vertices, allowed):
    if not vertices:
        return [()]
    first = vertices[0]
    result = []
    for other in vertices[1:]:
        item = edge(first, other)
        if item not in allowed:
            continue
        rest = tuple(value for value in vertices if value not in (first, other))
        result.extend((item, *tail) for tail in perfect_matchings(rest, allowed))
    return result


def global_colours(index):
    result = []
    for _ in VERTICES:
        result.append(index % 3)
        index //= 3
    return tuple(result)


def local_states(order):
    result = []
    for index in range(81):
        value = index
        state = {}
        for vertex in order:
            state[vertex] = value % 3
            value //= 3
        result.append(state)
    return tuple(result)


def mixed(colours):
    return any(value != colours[0] for value in colours[1:])


def build_data():
    factors = tuple(tuple(edge(*item) for item in matching) for matching in FACTORS)
    residual = tuple(edge(*item) for item in RESIDUAL)
    graph = tuple(sorted(set(residual).union(*map(set, factors))))
    anchor = {item: colour for colour, matching in enumerate(factors) for item in matching}
    matchings = tuple(perfect_matchings(VERTICES, set(graph)))
    cross = tuple(matching for matching in matchings if any(item in anchor for item in matching))
    states = tuple(local_states(order) for order in CYCLE_ORDERS)
    cycle_matchings = []
    for order in CYCLE_ORDERS:
        allowed = {item for item in residual if item[0] in order and item[1] in order}
        found = tuple(perfect_matchings(order, allowed))
        if len(found) != 2:
            raise AssertionError("component is not a four-cycle")
        cycle_matchings.append(found)
    return {
        "factors": factors,
        "residual": residual,
        "graph": graph,
        "anchor": anchor,
        "matchings": matchings,
        "cross": cross,
        "states": states,
        "cycle_matchings": tuple(cycle_matchings),
    }


def compatible_keys(data, matching, colours):
    keys = []
    for item in matching:
        anchor_colour = data["anchor"].get(item)
        if anchor_colour is not None:
            if colours[item[0]] != anchor_colour or colours[item[1]] != anchor_colour:
                return None
        else:
            keys.append((item, colours[item[0]], colours[item[1]]))
    return tuple(keys)


def conjunction(model, values, name):
    term = model.NewBoolVar(name)
    for value in values:
        model.Add(term <= value)
    model.Add(term >= sum(values) - len(values) + 1)
    return term


def stabilizer(data):
    graph_set = frozenset(data["graph"])
    factor_sets = tuple(frozenset(matching) for matching in data["factors"])
    factor_index = {value: index for index, value in enumerate(factor_sets)}
    result = []
    for permutation in itertools.permutations(VERTICES):
        if frozenset(edge(permutation[u], permutation[v]) for u, v in graph_set) != graph_set:
            continue
        colour_image = []
        for matching in factor_sets:
            image = frozenset(edge(permutation[u], permutation[v]) for u, v in matching)
            target = factor_index.get(image)
            if target is None:
                break
            colour_image.append(target)
        else:
            if len(set(colour_image)) == 3:
                result.append((permutation, tuple(colour_image)))
    return tuple(result)


def transform_masks(masks, data, symmetry):
    permutation, colour_image = symmetry
    residual_index = {item: index for index, item in enumerate(data["residual"])}
    output = [0] * 8
    for source_index, item in enumerate(data["residual"]):
        target_u, target_v = permutation[item[0]], permutation[item[1]]
        target_index = residual_index[edge(target_u, target_v)]
        for row in range(3):
            for column in range(3):
                if not masks[source_index] & (1 << (3 * row + column)):
                    continue
                new_row, new_column = colour_image[row], colour_image[column]
                if target_u > target_v:
                    new_row, new_column = new_column, new_row
                output[target_index] |= 1 << (3 * new_row + new_column)
    return tuple(output)


def canonical(masks, data, symmetries):
    return min(transform_masks(masks, data, symmetry) for symmetry in symmetries)


def splitmix64(value):
    value = (value + 0x9E3779B97F4A7C15) & MASK64
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & MASK64
    return value ^ (value >> 31)


def partition_groups(size):
    seeds = (0x243F6A8885A308D3, 0x13198A2E03707344)
    groups = []
    for seed in seeds:
        selected = tuple(index for index in range(size) if splitmix64(index ^ seed) & 1)
        if not selected or len(selected) == size:
            raise AssertionError("degenerate parity partition")
        groups.append(selected)
    return tuple(groups)


def add_partition(model, ordered_variables, shard_id, shard_count):
    if shard_count != 4 or shard_id not in range(shard_count):
        raise ValueError("this worker requires exactly four shards")
    groups = partition_groups(len(ordered_variables))
    for bit, group in enumerate(groups):
        remainder = model.NewIntVar(0, 1, f"partition_remainder_{bit}")
        model.AddModuloEquality(remainder, sum(ordered_variables[index] for index in group), 2)
        model.Add(remainder == ((shard_id >> bit) & 1))
    return [len(group) for group in groups]


def build_model(data, support_size, shard_id, shard_count):
    model = cp_model.CpModel()
    support = {
        (item, row, column): model.NewBoolVar(f"x_{item[0]}_{item[1]}_{row}_{column}")
        for item in data["residual"]
        for row in range(3)
        for column in range(3)
    }
    for item in data["residual"]:
        model.Add(sum(support[item, row, column] for row in range(3) for column in range(3)) >= 1)

    term_variables = 0
    for colouring_index in range(3 ** 8):
        colours = global_colours(colouring_index)
        if not mixed(colours):
            continue
        terms = []
        fixed = 0
        for matching_index, matching in enumerate(data["matchings"]):
            keys = compatible_keys(data, matching, colours)
            if keys is None:
                continue
            if not keys:
                fixed += 1
                continue
            terms.append(conjunction(model, [support[key] for key in keys], f"t_{colouring_index}_{matching_index}"))
            term_variables += 1
        if fixed >= 2:
            continue
        if fixed == 1:
            model.Add(sum(terms) >= 1)
        elif terms:
            model.Add(sum(terms) != 1)

    cycle_one = []
    for cycle_index in range(2):
        one_rows = []
        for state_index, state in enumerate(data["states"][cycle_index]):
            terms = []
            for matching_index, matching in enumerate(data["cycle_matchings"][cycle_index]):
                terms.append(conjunction(
                    model,
                    [support[item, state[item[0]], state[item[1]]] for item in matching],
                    f"cycle_{cycle_index}_{state_index}_{matching_index}",
                ))
            one = model.NewBoolVar(f"cycle_one_{cycle_index}_{state_index}")
            model.AddAllowedAssignments(
                [terms[0], terms[1], one],
                ((0, 0, 0), (0, 1, 1), (1, 0, 1), (1, 1, 0)),
            )
            one_rows.append(one)
        cycle_one.append(tuple(one_rows))

    forbidden = [[False] * 81 for _ in range(81)]
    for first_index, first in enumerate(data["states"][0]):
        for second_index, second in enumerate(data["states"][1]):
            merged = first | second
            colours = tuple(merged[vertex] for vertex in VERTICES)
            if not mixed(colours):
                continue
            if any(compatible_keys(data, matching, colours) is not None for matching in data["cross"]):
                continue
            forbidden[first_index][second_index] = True

    escape_variables = 0
    for source_cycle in range(2):
        escapes = []
        for target_state in range(81):
            blocked_ones = [
                cycle_one[source_cycle][source_state]
                for source_state in range(81)
                if (forbidden[source_state][target_state] if source_cycle == 0 else forbidden[target_state][source_state])
            ]
            escape = model.NewBoolVar(f"escape_{source_cycle}_{target_state}")
            escapes.append(escape)
            escape_variables += 1
            for one in blocked_ones:
                model.Add(escape + one <= 1)
            model.Add(escape >= 1 - sum(blocked_ones))
        model.AddBoolOr(escapes)

    ordered_variables = list(support.values())
    model.Add(sum(ordered_variables) == support_size)
    partition_sizes = add_partition(model, ordered_variables, shard_id, shard_count)
    return model, support, term_variables, escape_variables, partition_sizes


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


class Collector(cp_model.CpSolverSolutionCallback):
    def __init__(self, support, data, symmetries, args, metadata, started):
        super().__init__()
        self.support = support
        self.data = data
        self.symmetries = symmetries
        self.args = args
        self.metadata = metadata
        self.started = started
        self.deadline = started + args.seconds
        self.next_checkpoint = started + args.checkpoint_seconds
        self.raw = 0
        self.orbits = {}
        self.hit_cap = False
        self.hit_deadline = False
        self.hit_signal = False

    def snapshot(self, status):
        orbits = [
            {
                "masks": list(masks),
                "edge_sizes": [mask.bit_count() for mask in masks],
                "labelled_multiplicity": multiplicity,
            }
            for masks, multiplicity in sorted(self.orbits.items())
        ]
        return {
            **self.metadata,
            "status": status,
            "complete_enumeration": False,
            "hit_cap": self.hit_cap,
            "hit_deadline": self.hit_deadline,
            "hit_signal": self.hit_signal,
            "wall_seconds": time.monotonic() - self.started,
            "raw_supports": self.raw,
            "support_orbits": len(orbits),
            "orbits": orbits,
        }

    def checkpoint(self, status="RUNNING"):
        atomic_json(self.args.output, self.snapshot(status))

    def OnSolutionCallback(self):
        self.raw += 1
        masks = []
        for item in self.data["residual"]:
            mask = 0
            for row in range(3):
                for column in range(3):
                    if self.Value(self.support[item, row, column]):
                        mask |= 1 << (3 * row + column)
            masks.append(mask)
        representative = canonical(tuple(masks), self.data, self.symmetries)
        self.orbits[representative] = self.orbits.get(representative, 0) + 1
        now = time.monotonic()
        if self.raw >= self.args.cap:
            self.hit_cap = True
            self.checkpoint("CAP_REACHED")
            self.StopSearch()
        elif now >= self.deadline:
            self.hit_deadline = True
            self.checkpoint("DEADLINE_REACHED")
            self.StopSearch()
        elif self.raw % self.args.checkpoint_every == 0 or now >= self.next_checkpoint:
            self.checkpoint()
            self.next_checkpoint = now + self.args.checkpoint_seconds


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--support", type=int, required=True)
    parser.add_argument("--shard-id", type=int, required=True)
    parser.add_argument("--shard-count", type=int, default=4)
    parser.add_argument("--seconds", type=float, default=3240.0)
    parser.add_argument("--cap", type=int, default=2_000_000)
    parser.add_argument("--checkpoint-every", type=int, default=5_000)
    parser.add_argument("--checkpoint-seconds", type=float, default=60.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 0 <= args.support <= 72:
        raise ValueError("support is outside the 72-coordinate range")

    data = build_data()
    symmetries = stabilizer(data)
    model, support, term_variables, escape_variables, partition_sizes = build_model(
        data, args.support, args.shard_id, args.shard_count
    )
    started = time.monotonic()
    metadata = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "mode": "exact_support_layer",
        "support": args.support,
        "shard_id": args.shard_id,
        "shard_count": args.shard_count,
        "partition_version": PARTITION_VERSION,
        "partition_group_sizes": partition_sizes,
        "stabilizer_size": len(symmetries),
        "term_variables": term_variables,
        "escape_variables": escape_variables,
    }
    collector = Collector(support, data, symmetries, args, metadata, started)
    collector.checkpoint("STARTING")
    solver = cp_model.CpSolver()
    solver.parameters.enumerate_all_solutions = True
    solver.parameters.num_search_workers = 1
    solver.parameters.max_time_in_seconds = args.seconds
    solver.parameters.random_seed = 1

    def stop_on_signal(_signum, _frame):
        collector.hit_signal = True
        collector.checkpoint("SIGNAL_RECEIVED")
        solver.StopSearch()

    signal.signal(signal.SIGTERM, stop_on_signal)
    signal.signal(signal.SIGINT, stop_on_signal)
    status = solver.Solve(model, collector)
    status_name = solver.StatusName(status)
    result = collector.snapshot(status_name)
    result["complete_enumeration"] = (
        status in (cp_model.OPTIMAL, cp_model.INFEASIBLE)
        and not collector.hit_cap
        and not collector.hit_deadline
        and not collector.hit_signal
    )
    result["branches"] = solver.NumBranches()
    result["conflicts"] = solver.NumConflicts()
    atomic_json(args.output, result)
    print(json.dumps({key: value for key, value in result.items() if key != "orbits"}, indent=2))
    return 0 if result["complete_enumeration"] else 2


if __name__ == "__main__":
    sys.exit(main())
