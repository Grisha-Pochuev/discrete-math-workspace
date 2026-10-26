#!/usr/bin/env python3
"""Independently replay a generic exact torus Nullstellensatz certificate."""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path


def canonical_digest(payload: object) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def load_hashed(path: Path, expected=None):
    payload = json.loads(path.read_text(encoding="utf-8"))
    recorded = payload.pop("canonical_outcome_sha256")
    observed = canonical_digest(payload)
    payload["canonical_outcome_sha256"] = recorded
    if recorded != observed or (expected is not None and recorded != expected):
        raise AssertionError(f"digest mismatch for {path}")
    return payload


def decode(records, variable_count):
    result = {}
    for term in records:
        exponent = tuple(int(value) for value in term["exponent"])
        if len(exponent) != variable_count or any(value < 0 for value in exponent):
            raise AssertionError("invalid exponent")
        if exponent in result:
            raise AssertionError("duplicate exponent")
        coefficient = Fraction(term["coefficient"])
        if not coefficient:
            raise AssertionError("explicit zero coefficient")
        result[exponent] = coefficient
    return result


def add_product(total, left, right):
    for left_exponent, left_coefficient in left.items():
        for right_exponent, right_coefficient in right.items():
            exponent = tuple(
                left_value + right_value
                for left_value, right_value in zip(left_exponent, right_exponent)
            )
            total[exponent] = total.get(exponent, Fraction(0)) + left_coefficient * right_coefficient
            if not total[exponent]:
                del total[exponent]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    parser.add_argument("--spec-sha", required=True)
    parser.add_argument("--certificate", required=True)
    args = parser.parse_args()
    spec = load_hashed(Path(args.spec), args.spec_sha)
    certificate = load_hashed(Path(args.certificate))
    if certificate["spec_sha256"] != args.spec_sha:
        raise AssertionError("certificate/spec identity mismatch")
    pair = tuple(certificate["pair"])
    systems = [system for system in spec["systems"] if tuple(system["bits"]) == pair]
    if len(systems) != 1:
        raise AssertionError("certificate pair is absent or duplicated")
    system = dict(systems[0])
    system_sha = system.pop("system_sha256")
    if canonical_digest(system) != system_sha or certificate["system_sha256"] != system_sha:
        raise AssertionError("certificate/system identity mismatch")
    rank = int(system["effective_rank"])
    variable_count = rank + 1
    zero = (0,) * variable_count
    generators = [
        {(0,) + exponent: coefficient for exponent, coefficient in decode(
            record["polynomial"], rank
        ).items()}
        for record in system["generators"]
    ]
    generators.append({(1,) + (1,) * rank: Fraction(1), zero: Fraction(-1)})
    if len(generators) != int(certificate["generator_count_including_saturation"]):
        raise AssertionError("generator count mismatch")
    multipliers = {}
    for record in certificate["multipliers"]:
        index = int(record["generator_index"])
        if index < 0 or index >= len(generators) or index in multipliers:
            raise AssertionError("invalid multiplier index")
        multipliers[index] = decode(record["polynomial"], variable_count)
    if len(multipliers) != int(certificate["certificate_multiplier_count"]):
        raise AssertionError("multiplier count mismatch")
    if sum(len(polynomial) for polynomial in multipliers.values()) != int(
        certificate["certificate_term_count"]
    ):
        raise AssertionError("multiplier term count mismatch")
    total = {}
    for index, multiplier in multipliers.items():
        add_product(total, multiplier, generators[index])
    if total != {zero: Fraction(1)}:
        raise AssertionError("certificate identity does not equal one")
    print(json.dumps({
        "accepted": True,
        "pair": list(pair),
        "certificate_sha256": certificate["canonical_outcome_sha256"],
        "certificate_terms_replayed": certificate["certificate_term_count"],
        "identity": "1",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
