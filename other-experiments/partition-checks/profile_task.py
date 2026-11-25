import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import Counter, deque
from functools import cache, lru_cache
from fractions import Fraction as Q
from itertools import combinations
from json import dumps, loads
from math import ceil, comb
from pathlib import Path
from time import monotonic

HERE = Path(__file__).resolve().parent
SETTINGS = loads((HERE / "profile_grid.json").read_bytes())
PAIR_LIMITS = tuple(combinations(range(7), 2))


def minimum_cost(order):
    if order < 21:
        return 0
    return 5 if order == 21 else 20 * (order - 21)

def vectors(capacities, total):
    if not capacities:
        if total == 0:
            yield ()
        return
    rest = sum(capacities[1:])
    for value in range(max(0, total - rest), min(total, capacities[0]) + 1):
        for other in vectors(capacities[1:], total - value):
            yield value, *other

class Flow:
    def __init__(self):
        self.edges = []

    def vertex(self):
        self.edges.append([])
        return len(self.edges) - 1

    def edge(self, a, b, cap):
        self.edges[a].append([b, cap, len(self.edges[b])])
        self.edges[b].append([a, 0, len(self.edges[a]) - 1])

    def maximum(self, source, sink, limit):
        total = 0
        while total < limit:
            dist = [-1] * len(self.edges)
            dist[source] = 0
            queue = deque([source])
            while queue:
                a = queue.popleft()
                for b, cap, _ in self.edges[a]:
                    if cap and dist[b] < 0:
                        dist[b] = dist[a] + 1
                        queue.append(b)
            if dist[sink] < 0:
                break
            visit = [0] * len(dist)

            def augment(a, capacity):
                if a == sink:
                    return capacity
                while visit[a] < len(self.edges[a]):
                    arc = self.edges[a][visit[a]]
                    b, cap, back = arc
                    if cap and dist[b] == dist[a] + 1:
                        delta = augment(b, min(capacity, cap))
                        if delta:
                            arc[1] -= delta
                            self.edges[b][back][1] += delta
                            return delta
                    visit[a] += 1
                return 0

            while total < limit:
                delta = augment(source, limit - total)
                if not delta:
                    break
                total += delta
        return total

def pair_caps(di, dj, short, lower):
    upper = 19 - dj
    if short >= 2:
        upper = min(upper, 1 + (1 + di * dj) // (short - 1),
                    (21 + di * dj) // short)
    elif short == 1:
        upper = min(upper, 21 + di * dj)
    return upper if upper >= lower else 0

@lru_cache(maxsize=8192)
def room(deficit, bounds):
    marks = sorted(bounds)
    running = 0
    for count, mark in enumerate(marks, 1):
        running += mark
        quotient, remainder = divmod(count, 7)
        forced_cost = 7 * comb(quotient, 2) + quotient * remainder
        if running + comb(count, 2) - forced_cost < minimum_cost(20 - deficit + count):
            return False
    return True

@lru_cache(maxsize=8192)
def capacity(deficit, caps, threshold, row_count):
    return max((n for n in range(row_count - len(caps) + 1)
                if room(deficit, caps + (threshold,) * n)), default=0)

@lru_cache(maxsize=8192)
def threshold_candidates(profile, row_count):
    choices = []
    for deficit in profile:
        row = (5,) if deficit == 0 else range(2, min(12, 20 - deficit) + 1)
        choices.append({threshold: capacity(deficit, (), threshold - 1, row_count)
                        for threshold in row})

    def visit(prefix, counts):
        i = len(prefix)
        if i == 7:
            yield sum(counts), prefix, counts
            return
        lo = prefix[-1] if i and profile[i] == profile[i-1] else 0
        for threshold, count in choices[i].items():
            if threshold < lo:
                continue
            if all((threshold - 1) * (previous - 1) > 1 + profile[i] * profile[j]
                   for j, previous in enumerate(prefix)):
                yield from visit(prefix + (threshold,), counts + (count,))

    best = []
    for candidate in visit((), ()):
        if len(best) < 192 or candidate < best[-1]:
            best.append(candidate)
            best.sort()
            del best[192:]
    return best

def propagated_groups(profile, thresholds, base_counts, double_counts, row_count, width):
    entry_cap = tuple(k - 1 for k in thresholds)
    while True:
        caps = tuple(tuple(sorted((upper,) * (s - h) + (k - 1,) * h))
                     for upper, s, h, k in zip(entry_cap, base_counts, double_counts, thresholds))
        if any(not room(d, bounds) for d, bounds in zip(profile, caps)):
            return "prefix", (), ()
        allowed = tuple(tuple(n for n in range(k, 20 - d)
                              if capacity(d, bounds, n, row_count))
                        for d, bounds, k in zip(profile, caps, thresholds))
        if any(not vals and s + width < d + 2 for vals, s, d in zip(allowed, base_counts, profile)):
            return "pivot", (), ()
        new_caps = tuple(
            min(upper, max((mark for mark in range(upper + 1)
                            if any(i != j and opts and pair_caps(d, profile[j], mark, opts[0])
                                   for j, opts in enumerate(allowed))), default=-1))
            if s > h else upper
            for i, (d, s, h, upper) in enumerate(zip(profile, base_counts, double_counts, entry_cap))
        )
        if min(new_caps) < 0:
            return "partner", (), ()
        if new_caps == entry_cap:
            break
        entry_cap = new_caps

    groups = []
    for i, (d, k, s, h, upper) in enumerate(zip(profile, thresholds, base_counts, double_counts, entry_cap)):
        singles = s - h
        if not singles:
            continue
        levels = [0] * singles
        for mark in range(1, upper + 1):
            least = next(count for count in range(singles + 1)
                         if room(d, (mark - 1,) * (singles - count)
                                 + (upper,) * count + (k - 1,) * h))
            for index in range(least):
                levels[index] = mark
        for mark, count in Counter(levels).items():
            options = tuple((j, max_length) for j, opts in enumerate(allowed)
                            if i != j and opts
                            and (max_length := pair_caps(d, profile[j], mark, opts[0])))
            if not options:
                return "partner", (), ()
            groups.append((i, count, options))
    return "flow", caps, groups

def flow_fits(profile, base_counts, caps, groups, row_count, width, excess, extras=None):
    total = sum(count for _, count, _ in groups)
    if extras is None:
        extras = (0,) * len(profile)
    required = tuple(max(0, 2 + d - s - t)
                     for d, s, t in zip(profile, base_counts, extras, strict=True))
    mandatory = tuple(max(0, value - width) for value in required)
    free = total - sum(required) + 2 * width + excess
    if free < 0 or sum(mandatory) > total:
        return False
    network = Flow()
    source, sink, surplus, flexible = (network.vertex() for _ in range(4))
    network.edge(surplus, flexible, free)
    network.edge(flexible, sink, total - sum(mandatory))
    receivers = {}
    for j, (d, bounds) in enumerate(zip(profile, caps)):
        previous = None
        old_cap = 0
        for length in sorted({length for _, _, options in groups
                              for row, length in options if row == j}):
            node = network.vertex()
            receivers[j, length] = node
            if previous is not None:
                network.edge(previous, node, old_cap)
            previous = node
            old_cap = capacity(d, bounds, length, row_count)
        if previous is not None:
            endpoint = network.vertex()
            network.edge(previous, endpoint, old_cap)
            network.edge(endpoint, sink, mandatory[j])
            network.edge(endpoint, flexible, required[j] - mandatory[j])
            network.edge(endpoint, surplus, old_cap)
    for _, count, options in groups:
        node = network.vertex()
        network.edge(source, node, count)
        for option in options:
            network.edge(node, receivers[option], count)
    return network.maximum(source, sink, total) == total

def satisfies_margin(lengths, cuts):
    assert len(lengths) >= 2 and len(lengths) == len(cuts) and min(lengths) > 0
    risk = {(i, j): Q(cuts[i][j], lengths[i] * lengths[j])
            for i, j in combinations(range(len(lengths)), 2)}
    if sum(risk.values()) < 1:
        return True
    for pivot, length in enumerate(lengths):
        rest = tuple(i for i in range(len(lengths)) if i != pivot)
        remaining = {pair: price for pair, price in risk.items() if pivot not in pair}
        gap = 1 - sum(remaining.values())
        if gap <= 0:
            continue
        cost = min(lengths[i] * gap / (gap + sum(
            price for pair, price in remaining.items() if i in pair)) for i in rest)
        if sum(cuts[pivot][i] for i in rest) < length * ceil(cost):
            return True
    return False


def block_layout(groups, spread):
    def visit(remaining, budget, ceiling):
        if remaining == 0:
            if budget == 0:
                yield ()
            return
        for value in range(min(ceiling, budget - (remaining - 1) * 3), 2, -1):
            for rest in visit(remaining - 1, budget - value, value):
                yield (value, *rest)
    yield from visit(groups, 2 * groups + spread, 7)


@lru_cache(maxsize=8192)
def candidate_masks(profile, caps, width):
    lower = []
    maximum = []
    for d, marks in zip(profile, caps):
        allowed = tuple(length for length in range(20-d) if room(d, marks + (length,)))
        lower.append(min(allowed, default=20))
        maximum.append(capacity(d, marks, 19-d, len(marks) + width))
    choices = {}
    for size in range(3, 8):
        available = []
        for support in combinations(range(7), size):
            if not all(maximum[i] for i in support):
                continue
            lengths = tuple(lower[i] for i in support)
            cuts = tuple(tuple(20 + profile[i] * profile[j] if i != j else 0 for j in support)
                         for i in support)
            if min(lengths) > 0 and satisfies_margin(lengths, cuts):
                continue
            available.append(support)
        choices[size] = tuple(available)
    return tuple(maximum), choices


class Limit(Exception):
    pass


def check_stamps(profile, base_counts, caps, groups, count, width, excess, until):
    if width == 0:
        return flow_fits(profile, base_counts, caps, groups, count, 0, 0)
    maximum, options = candidate_masks(profile, caps, width)
    @cache
    def exact(stamps):
        return flow_fits(profile, base_counts, caps, groups, count, 0, 0, extras=stamps)

    for shape in block_layout(width, excess):
        @cache
        def visit(index, previous, stamps):
            if monotonic() >= until:
                raise Limit
            if index == len(shape):
                return exact(stamps)
            size = shape[index]
            first = previous if index and size == shape[index-1] else 0
            for pos in range(first, len(options[size])):
                support = options[size][pos]
                if any(stamps[i] == maximum[i] for i in support):
                    continue
                nxt = tuple(value + (i in support) for i,value in enumerate(stamps))
                if visit(index + 1, pos, nxt):
                    return True
            return False
        if visit(0, 0, (0,) * 7):
            return True
    return False


def test_task(work):
    row, seconds = work
    tag, profile, width, excess = row
    d = sum(profile)
    count, weight = d + 8 - width, d + 2 + excess
    until = monotonic() + seconds
    attempts, visited = 0, 0
    try:
        for total_short, thresholds, limits in threshold_candidates(tuple(profile), count):
            if total_short > count + 6:
                break
            attempts += 1
            found = False
            for total in range(count, total_short + 1):
                if found:
                    break
                delta = total - count
                for base_counts in vectors(limits, total):
                    if found:
                        break
                    if any(profile[i] == profile[i+1] and thresholds[i] == thresholds[i+1]
                           and base_counts[i] > base_counts[i+1] for i in range(6)):
                        continue
                    if sum(max(0, short - h - 2) for h, short in zip(profile, base_counts)) > weight:
                        continue
                    for double_counts in vectors(tuple(min(delta, n) for n in base_counts), 2*delta):
                        if monotonic() >= until:
                            raise Limit
                        if any(profile[i] == profile[i+1] and thresholds[i] == thresholds[i+1]
                               and base_counts[i] == base_counts[i+1] and double_counts[i] > double_counts[i+1] for i in range(6)):
                            continue
                        visited += 1
                        result, caps, groups = propagated_groups(profile, thresholds, base_counts, double_counts, count, width)
                        if result == "flow" and flow_fits(profile, base_counts, caps, groups, count, width, excess):
                            if check_stamps(tuple(profile), base_counts, caps, groups, count, width, excess, until):
                                found = True
                                break
            if not found:
                return {"id": tag, "status": "closed", "thresholds": thresholds,
                        "attempts": attempts, "visited": visited}
    except Limit:
        return {"id": tag, "status": "deferred", "attempts": attempts, "visited": visited}
    return {"id": tag, "status": "open", "attempts": attempts, "visited": visited}


def main():
    assert __debug__
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane", type=int, choices=range(20), default=0)
    parser.add_argument("--workers", type=int, choices=range(1, 5), default=4)
    parser.add_argument("--seconds", type=int, default=900)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--id", type=int)
    args = parser.parse_args()
    assert args.seconds > 0
    jobs = SETTINGS["tasks"]
    assert [row[0] for row in jobs] == list(range(len(jobs)))
    if args.id is not None:
        jobs = [jobs[args.id]]
    else:
        jobs = jobs[args.lane::20]
    assert jobs
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def write(results):
        for item in results:
            line = dumps(item, separators=(",", ":"))
            print(line, flush=True)
            with args.output.open("a", encoding="utf-8", newline="\n") as stream:
                print(line, file=stream)

    assert not args.output.exists()
    if args.workers == 1:
        write(test_task((job, args.seconds)) for job in jobs)
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            pending = [pool.submit(test_task, (job, args.seconds)) for job in jobs]
            write(future.result() for future in as_completed(pending))


if __name__ == "__main__":
    main()

