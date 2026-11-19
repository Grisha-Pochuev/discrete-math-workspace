"""Validate an exact bounded vector-sum implementation against enumeration."""

import argparse
import itertools
import random


def reachable(options, steps, limits):
    """Return (first, second) keys with a bit for each reachable third sum."""
    first_limit, second_limit, third_limit = limits
    third_mask = (1 << (third_limit + 1)) - 1
    layer = {(0, 0): 1}
    for _ in range(steps):
        following = {}
        for (first, second), bits in layer.items():
            for a, b, c in options:
                key = first + a, second + b
                if key[0] > first_limit or key[1] > second_limit:
                    continue
                shifted = (bits << c) & third_mask
                if shifted:
                    following[key] = following.get(key, 0) | shifted
        layer = following
    return layer


def enumerate_sums(options, steps, limits):
    result = set()
    for sequence in itertools.product(options, repeat=steps):
        total = tuple(sum(item[axis] for item in sequence) for axis in range(3))
        if all(value <= limit for value, limit in zip(total, limits)):
            result.add(total)
    return result


def unpack(layer):
    return {
        (first, second, third)
        for (first, second), bits in layer.items()
        for third in range(bits.bit_length())
        if (bits >> third) & 1
    }


def verify(seed, samples):
    rng = random.Random(seed)
    controls = [
        ([], 0, (0, 0, 0)),
        ([], 1, (0, 0, 0)),
        ([(0, 0, 0), (0, 0, 1)], 4, (0, 0, 2)),
        ([(3, 0, 0), (0, 3, 0), (0, 0, 3)], 2, (5, 5, 5)),
    ]
    for _ in range(samples):
        options = sorted({
            tuple(rng.randrange(5) for _ in range(3))
            for _ in range(rng.randrange(1, 9))
        })
        steps = rng.randrange(6)
        limits = tuple(rng.randrange(2, 18) for _ in range(3))
        controls.append((options, steps, limits))

    for options, steps, limits in controls:
        expected = enumerate_sums(options, steps, limits)
        actual = unpack(reachable(options, steps, limits))
        if actual != expected:
            raise AssertionError((seed, options, steps, limits, actual ^ expected))
    print(f"seed={seed} controls={len(controls)} status=pass")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--samples", type=int, default=300)
    args = parser.parse_args()
    verify(args.seed, args.samples)
