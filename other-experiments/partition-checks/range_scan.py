"""Cross-check bounded vector reachability over a sharded parameter grid."""

import argparse
from concurrent.futures import ProcessPoolExecutor
from itertools import product

from check import reachable, unpack


def reference(options, steps, limits):
    a_limit, b_limit, c_limit = limits
    layer = {(0, 0, 0)}
    for _ in range(steps):
        layer = {
            (a + x, b + y, c + z)
            for a, b, c in layer
            for x, y, z in options
            if a + x <= a_limit and b + y <= b_limit and c + z <= c_limit
        }
    return layer


def scan_lane(work):
    shard, lane, levels = work
    checks = 0
    states = 0
    for width, steps, scale in product(range(5, 5 + levels), (6, 12, 18, 24), (1, 2, 3)):
        options = sorted({
            (x, (x * (2 * lane + 1) + width) % (3 + shard % 5),
             (x * x + x * (shard + lane) + scale) % (4 + scale))
            for x in range(width)
        } | {(0, 0, 0), (0, 1 + lane, scale)})
        limits = (6 + shard + scale * 2, 5 + 3 * scale + lane, 11 + scale * 4)
        expected = reference(options, steps, limits)
        actual = unpack(reachable(options, steps, limits))
        if actual != expected:
            raise AssertionError((shard, lane, width, steps, scale, actual ^ expected))
        checks += 1
        states += len(actual)
    return lane, checks, states


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shard", type=int, choices=range(20), required=True)
    parser.add_argument("--workers", type=int, choices=range(1, 5), default=4)
    parser.add_argument("--levels", type=int, choices=range(1, 13), default=10)
    args = parser.parse_args()
    work = [(args.shard, lane, args.levels) for lane in range(4)]

    def report(results):
        for lane, checks, states in results:
            print(f"shard={args.shard} lane={lane} checks={checks} states={states}", flush=True)

    if args.workers == 1:
        report(map(scan_lane, work))
        return
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        report(pool.map(scan_lane, work))


if __name__ == "__main__":
    main()
