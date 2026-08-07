#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import random
import re
import zipfile

import numpy as np


N = 6
D = 3
MONO = (0, 364, 728)
MONO_SET = set(MONO)
HEADER = re.compile(
    r"# orbit (?P<orbit>\d+) limit (?P<limit>\d+) status (?P<status>\w+) "
    r"nodes (?P<nodes>\d+) seen (?P<seen>\d+) seconds (?P<seconds>[0-9.]+) "
    r"shard (?P<shard>\d+)/(?P<shards>\d+) split_size (?P<split>\d+) "
    r"max_seen (?P<max_seen>\d+)"
)


def perfect_matchings(vertices: tuple[int, ...]):
    if not vertices:
        yield ()
        return
    left = vertices[0]
    for position in range(1, len(vertices)):
        right = vertices[position]
        rest = vertices[1:position] + vertices[position + 1:]
        for tail in perfect_matchings(rest):
            yield ((left, right),) + tail


MATCHINGS = tuple(perfect_matchings(tuple(range(N))))
COLOURINGS = tuple(itertools.product(range(D), repeat=N))
EDGES = tuple((i, j) for i in range(N) for j in range(i + 1, N))
EDGE_POS = {edge: index for index, edge in enumerate(EDGES)}
NV = len(EDGES) * D * D
NC = len(COLOURINGS)


def var_index(i: int, j: int, a: int, b: int) -> int:
    if i > j:
        i, j, a, b = j, i, b, a
    return (EDGE_POS[(i, j)] * D + a) * D + b


TERM_VARS = np.empty((NC, len(MATCHINGS), N // 2), dtype=np.int16)
for colouring_index, colours in enumerate(COLOURINGS):
    for matching_index, matching in enumerate(MATCHINGS):
        TERM_VARS[colouring_index, matching_index] = [
            var_index(i, j, colours[i], colours[j]) for i, j in matching
        ]


def active_terms(mask: int) -> np.ndarray:
    support = np.zeros(NV, dtype=bool)
    support[[v for v in range(NV) if mask >> v & 1]] = True
    return np.all(support[TERM_VARS], axis=2)


def is_closed(mask: int) -> bool:
    counts = active_terms(mask).sum(axis=1)
    return not any(int(counts[row]) == 1 for row in range(NC) if row not in MONO_SET)


def rank_mod_prime(matrix: np.ndarray, prime: int = 1_000_003) -> int:
    a = np.asarray(matrix, dtype=np.int64).copy() % prime
    rows, columns = a.shape
    rank = 0
    for column in range(columns):
        pivot = next((row for row in range(rank, rows) if a[row, column]), None)
        if pivot is None:
            continue
        a[[rank, pivot]] = a[[pivot, rank]]
        inverse = pow(int(a[rank, column]), prime - 2, prime)
        a[rank] = (a[rank] * inverse) % prime
        for row in range(rows):
            if row != rank and a[row, column]:
                a[row] = (a[row] - a[row, column] * a[rank]) % prime
        rank += 1
        if rank == rows:
            break
    return rank


def bareiss_determinant(matrix: np.ndarray) -> int:
    a = [list(map(int, row)) for row in np.asarray(matrix)]
    size = len(a)
    if size == 0:
        return 1
    sign = 1
    previous = 1
    for k in range(size - 1):
        if a[k][k] == 0:
            pivot = next((row for row in range(k + 1, size) if a[row][k]), None)
            if pivot is None:
                return 0
            a[k], a[pivot] = a[pivot], a[k]
            sign = -sign
        value = a[k][k]
        for i in range(k + 1, size):
            for j in range(k + 1, size):
                numerator = a[i][j] * value - a[i][k] * a[k][j]
                assert numerator % previous == 0
                a[i][j] = numerator // previous
        previous = value
        for i in range(k + 1, size):
            a[i][k] = 0
    return sign * a[-1][-1]


def exact_unimodular_basis(matrix: np.ndarray, seed: int):
    matrix = np.asarray(matrix, dtype=np.int64)
    rank = rank_mod_prime(matrix)

    def greedy(row_order, column_order):
        rows: list[int] = []
        current_rank = 0
        for index in row_order:
            if rank_mod_prime(matrix[rows + [index]]) > current_rank:
                rows.append(index)
                current_rank += 1
            if current_rank == rank:
                break
        columns: list[int] = []
        current_rank = 0
        for index in column_order:
            candidate = matrix[np.ix_(rows, columns + [index])]
            if rank_mod_prime(candidate) > current_rank:
                columns.append(index)
                current_rank += 1
            if current_rank == rank:
                break
        return rows, columns

    attempts = [(list(range(matrix.shape[0])), list(range(matrix.shape[1])))]
    rng = random.Random(seed)
    for _ in range(256):
        row_order = list(range(matrix.shape[0]))
        column_order = list(range(matrix.shape[1]))
        rng.shuffle(row_order)
        rng.shuffle(column_order)
        attempts.append((row_order, column_order))

    for row_order, column_order in attempts:
        rows, columns = greedy(row_order, column_order)
        if len(rows) != rank or len(columns) != rank:
            continue
        pivot = matrix[np.ix_(rows, columns)]
        if abs(bareiss_determinant(pivot)) != 1:
            continue
        inverse = np.rint(np.linalg.inv(pivot.astype(float))).astype(np.int64)
        identity = np.eye(rank, dtype=np.int64)
        assert np.array_equal(pivot @ inverse, identity)
        assert np.array_equal(inverse @ pivot, identity)
        return tuple(rows), tuple(columns), matrix[rows], inverse
    return None


def row_coordinates(mask: int):
    supported = [variable for variable in range(NV) if mask >> variable & 1]
    position = {variable: index for index, variable in enumerate(supported)}
    active = active_terms(mask)
    rows: dict[int, list[np.ndarray]] = {}
    for row in range(NC):
        terms = [int(term) for term in np.flatnonzero(active[row])]
        if not terms:
            continue
        reference = terms[0]
        coordinates = []
        for term in terms:
            difference = np.zeros(len(supported), dtype=np.int64)
            for variable in TERM_VARS[row, term]:
                difference[position[int(variable)]] += 1
            for variable in TERM_VARS[row, reference]:
                difference[position[int(variable)]] -= 1
            coordinates.append(difference)
        rows[row] = coordinates
    return supported, rows


def analyse_support(mask: int) -> str:
    supported, rows = row_coordinates(mask)
    relations = []
    for row, coordinates in rows.items():
        if row not in MONO_SET and len(coordinates) == 2:
            relations.append((coordinates[1] - coordinates[0], 1))
    if not relations:
        return "unresolved"

    relation_matrix = np.asarray([vector for vector, _ in relations], dtype=np.int64)
    basis_data = exact_unimodular_basis(relation_matrix, mask & 0xFFFFFFFF)
    if basis_data is None:
        return "unresolved"
    basis_rows, pivot_columns, basis, inverse = basis_data
    basis_signs = np.asarray([relations[index][1] for index in basis_rows], dtype=np.int64)

    def reduce_vector(vector: np.ndarray):
        coefficients = np.asarray(vector, dtype=np.int64)[list(pivot_columns)] @ inverse
        remainder = np.asarray(vector, dtype=np.int64) - coefficients @ basis
        assert not np.any(remainder[list(pivot_columns)])
        sign = int(coefficients @ basis_signs) & 1
        return tuple(int(value) for value in remainder), sign

    for vector, prescribed_sign in relations:
        remainder, sign = reduce_vector(vector)
        assert not any(remainder)
        if sign != prescribed_sign:
            return "inconsistent_signs"

    for row, coordinates in rows.items():
        reduced: Counter[tuple[int, ...]] = Counter()
        for vector in coordinates:
            remainder, sign = reduce_vector(vector)
            reduced[remainder] += -1 if sign else 1
        reduced = Counter({exponent: coefficient for exponent, coefficient in reduced.items()
                           if coefficient})
        if row in MONO_SET and not reduced:
            return "target_zero"
        if row not in MONO_SET and len(reduced) == 1:
            return "mixed_monomial"
    return "unresolved"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    root = Path(__file__).resolve().parent
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    checksum_lines = (root / "checksums.sha256").read_text(encoding="utf-8").splitlines()
    checksums = {name: digest for digest, name in (line.split() for line in checksum_lines)}
    archives = sorted((root / "raw").glob("data-*.zip"), key=lambda path: int(path.stem[5:]))
    assert len(archives) == summary["artifacts"] == len(checksums) == 20
    for archive in archives:
        relative = archive.relative_to(root).as_posix()
        assert sha256(archive) == checksums[relative]

    records = []
    supports = []
    nodes = 0
    states = 0
    engine_seconds = 0.0
    max_rss = 0
    max_swap = 0
    jobs = set()
    task_names = set()
    unstarted = []

    for archive in archives:
        with zipfile.ZipFile(archive) as zf:
            manifest = json.loads(zf.read("manifest.json"))
            jobs.add(int(manifest["job_id"]))
            unstarted.extend(manifest["unstarted"])
            records.extend(manifest["records"])
            for record in manifest["records"]:
                assert record["name"] not in task_names
                task_names.add(record["name"])
                lines = zf.read(record["result"]).decode("utf-8").splitlines()
                match = HEADER.fullmatch(lines[0])
                assert match is not None
                header = match.groupdict()
                assert header["status"] == record["status"]
                assert int(header["orbit"]) == int(record["orbit"])
                assert int(header["limit"]) == int(record["limit"])
                assert int(header["shard"]) == int(record["shard"])
                assert int(header["shards"]) == int(record["shards"])
                nodes += int(header["nodes"])
                states += int(header["seen"])
                engine_seconds += float(header["seconds"])
                for line in lines[1:]:
                    size_text, mask_text = line.split()
                    mask = int(mask_text, 16)
                    assert int(size_text) == mask.bit_count()
                    assert is_closed(mask)
                    supports.append(mask)
            resource_lines = zf.read("resources.tsv").decode("utf-8").splitlines()[1:]
            for line in resource_lines:
                _, rss_text, _, swap_text, *_ = line.split("\t")
                max_rss = max(max_rss, int(rss_text))
                max_swap = max(max_swap, int(swap_text))

    status_counts = Counter(record["status"] for record in records)
    layer_counts = {
        str(limit): Counter(record["status"] for record in records if int(record["limit"]) == limit)
        for limit in (26, 27)
    }
    unique_supports = set(supports)
    outcomes = {mask: analyse_support(mask) for mask in unique_supports}
    outcome_counts = Counter(outcomes.values())
    size_counts = Counter(mask.bit_count() for mask in unique_supports)
    size26_outcomes = Counter(outcomes[mask] for mask in unique_supports if mask.bit_count() == 26)
    size27_outcomes = Counter(outcomes[mask] for mask in unique_supports if mask.bit_count() == 27)
    pending26 = sorted(record["name"] for record in records
                       if int(record["limit"]) == 26 and record["status"] == "capacity")

    assert jobs == set(range(20))
    assert not unstarted
    assert len(records) == len(task_names) == summary["tasks"]["recorded"] == 3584
    assert status_counts == {"complete": 2799, "capacity": 785}
    assert layer_counts["26"] == {"complete": 1513, "capacity": 23}
    assert layer_counts["27"] == {"complete": 1286, "capacity": 762}
    assert nodes == summary["search"]["nodes"] == 13_803_889_594
    assert states == summary["search"]["states"] == 13_267_771_404
    assert abs(engine_seconds - summary["search"]["engine_seconds"]) < 1e-6
    assert max_rss == summary["resources"]["max_combined_rss_bytes"] == 1_770_573_824
    assert max_swap == summary["resources"]["max_swap_used_bytes"] == 0
    assert len(supports) == summary["supports"]["occurrences"] == 297
    assert len(unique_supports) == summary["supports"]["unique"] == 46
    assert size_counts == {21: 4, 23: 3, 25: 13, 26: 12, 27: 14}
    assert outcome_counts == {"inconsistent_signs": 7, "target_zero": 30, "mixed_monomial": 9}
    assert size26_outcomes == {"target_zero": 8, "mixed_monomial": 4}
    assert size27_outcomes == {"target_zero": 9, "mixed_monomial": 5}
    assert pending26 == summary["pending_layer_26"]

    print("PASS: 20 artifact checksums")
    print("PASS: 3,584 task records, no missing or duplicate task")
    print("PASS: 13,803,889,594 nodes and 13,267,771,404 states")
    print("PASS: 46 unique closed supports have exact obstructions")
    print("PASS: all 12 size-26 and all 14 size-27 supports are excluded")
    print("OPEN: 23 layer-26 tasks and 762 layer-27 tasks ended at capacity")


if __name__ == "__main__":
    main()
