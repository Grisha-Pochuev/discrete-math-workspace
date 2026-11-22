#!/usr/bin/env python3
"""Produce one portable exact Nullstellensatz certificate from a JSON system."""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import heapq
import json
from pathlib import Path
import time


Monomial = tuple[int, ...]
Polynomial = dict[Monomial, Fraction]


def canonical_digest(payload: object) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def clean(polynomial: Polynomial) -> Polynomial:
    return {monomial: coefficient for monomial, coefficient in polynomial.items() if coefficient}


def add(left: Polynomial, right: Polynomial, weight: Fraction = Fraction(1)) -> Polynomial:
    result = dict(left)
    for monomial, coefficient in right.items():
        result[monomial] = result.get(monomial, Fraction(0)) + weight * coefficient
        if not result[monomial]:
            del result[monomial]
    return result


def multiply(polynomial: Polynomial, monomial: Monomial, coefficient=Fraction(1)) -> Polynomial:
    return clean({
        tuple(left + right for left, right in zip(source, monomial)): value * coefficient
        for source, value in polynomial.items()
    })


def order_key(monomial: Monomial):
    return sum(monomial), tuple(-value for value in reversed(monomial))


def leading(polynomial: Polynomial):
    monomial = max(polynomial, key=order_key)
    return monomial, polynomial[monomial]


def divides(left: Monomial, right: Monomial) -> bool:
    return all(a <= b for a, b in zip(left, right))


def difference(left: Monomial, right: Monomial) -> Monomial:
    return tuple(a - b for a, b in zip(left, right))


def lcm(left: Monomial, right: Monomial) -> Monomial:
    return tuple(max(a, b) for a, b in zip(left, right))


def coprime(left: Monomial, right: Monomial) -> bool:
    return all(min(a, b) == 0 for a, b in zip(left, right))


def representation_add(left, right, weight=Fraction(1)):
    return [add(a, b, weight) for a, b in zip(left, right)]


def representation_multiply(representation, monomial, coefficient=Fraction(1)):
    return [multiply(polynomial, monomial, coefficient) for polynomial in representation]


def replay(representation, generators):
    result = {}
    for multiplier, generator in zip(representation, generators):
        for monomial, coefficient in multiplier.items():
            result = add(result, multiply(generator, monomial, coefficient))
    return result


def reduce_with_representation(source, source_representation, basis, basis_representations, generators):
    polynomial = dict(source)
    remainder = {}
    quotients = [{} for _ in basis]
    while polynomial:
        monomial, coefficient = leading(polynomial)
        choices = []
        for index, basis_polynomial in enumerate(basis):
            basis_monomial, basis_coefficient = leading(basis_polynomial)
            if divides(basis_monomial, monomial):
                quotient = difference(monomial, basis_monomial)
                choices.append((order_key(quotient), index, basis_monomial, basis_coefficient))
        if not choices:
            remainder[monomial] = remainder.get(monomial, Fraction(0)) + coefficient
            del polynomial[monomial]
            continue
        _key, index, basis_monomial, basis_coefficient = min(choices)
        quotient_monomial = difference(monomial, basis_monomial)
        quotient_coefficient = coefficient / basis_coefficient
        quotients[index] = add(
            quotients[index], {quotient_monomial: quotient_coefficient}
        )
        polynomial = add(
            polynomial,
            multiply(basis[index], quotient_monomial),
            -quotient_coefficient,
        )
    representation = source_representation
    for quotient, basis_representation in zip(quotients, basis_representations):
        for monomial, coefficient in quotient.items():
            representation = representation_add(
                representation,
                representation_multiply(basis_representation, monomial, coefficient),
                Fraction(-1),
            )
    if replay(representation, generators) != remainder:
        raise AssertionError("remainder representation failed exact replay")
    return remainder, representation


def derive_identity(generators):
    generator_count = len(generators)
    variable_count = len(next(iter(generators[0])))
    zero = (0,) * variable_count
    basis = []
    representations = []
    for index, generator in enumerate(generators):
        _monomial, coefficient = leading(generator)
        normalized = multiply(generator, zero, 1 / coefficient)
        representation = [{} for _ in range(generator_count)]
        representation[index] = {zero: 1 / coefficient}
        basis.append(normalized)
        representations.append(representation)

    queue = []
    serial = 0
    for right in range(len(basis)):
        for left in range(right):
            common = lcm(leading(basis[left])[0], leading(basis[right])[0])
            heapq.heappush(queue, (sum(common), serial, left, right))
            serial += 1
    processed = 0
    coprime_skipped = 0
    while queue:
        _degree, _serial, left_index, right_index = heapq.heappop(queue)
        left_monomial, left_coefficient = leading(basis[left_index])
        right_monomial, right_coefficient = leading(basis[right_index])
        if coprime(left_monomial, right_monomial):
            coprime_skipped += 1
            continue
        processed += 1
        common = lcm(left_monomial, right_monomial)
        left_shift = difference(common, left_monomial)
        right_shift = difference(common, right_monomial)
        s_polynomial = add(
            multiply(basis[left_index], left_shift, 1 / left_coefficient),
            multiply(basis[right_index], right_shift, 1 / right_coefficient),
            Fraction(-1),
        )
        s_representation = representation_add(
            representation_multiply(
                representations[left_index], left_shift, 1 / left_coefficient
            ),
            representation_multiply(
                representations[right_index], right_shift, 1 / right_coefficient
            ),
            Fraction(-1),
        )
        remainder, representation = reduce_with_representation(
            s_polynomial, s_representation, basis, representations, generators
        )
        if not remainder:
            continue
        _monomial, coefficient = leading(remainder)
        remainder = multiply(remainder, zero, 1 / coefficient)
        representation = representation_multiply(representation, zero, 1 / coefficient)
        if replay(representation, generators) != remainder:
            raise AssertionError("normalized basis representation failed exact replay")
        if len(remainder) == 1 and zero in remainder:
            representation = representation_multiply(
                representation, zero, 1 / remainder[zero]
            )
            if replay(representation, generators) != {zero: Fraction(1)}:
                raise AssertionError("final identity failed exact replay")
            return representation, len(basis), processed, coprime_skipped
        new_index = len(basis)
        basis.append(remainder)
        representations.append(representation)
        for old_index in range(new_index):
            common = lcm(leading(basis[old_index])[0], leading(remainder)[0])
            heapq.heappush(queue, (sum(common), serial, old_index, new_index))
            serial += 1
        if len(basis) > 10000:
            raise RuntimeError("basis growth limit exceeded")
    raise RuntimeError("Buchberger basis completed without an identity")


def decode_polynomial(records, variable_count):
    result = {}
    for term in records:
        exponent = tuple(int(value) for value in term["exponent"])
        if len(exponent) != variable_count or any(value < 0 for value in exponent):
            raise AssertionError("invalid generator exponent")
        if exponent in result:
            raise AssertionError("duplicate generator exponent")
        coefficient = Fraction(term["coefficient"])
        if not coefficient:
            raise AssertionError("explicit zero generator coefficient")
        result[exponent] = coefficient
    return result


def encode_polynomial(polynomial):
    return [
        {"exponent": list(exponent), "coefficient": str(coefficient)}
        for exponent, coefficient in sorted(polynomial.items())
    ]


def load_system(path: Path, pair, expected_spec_sha: str):
    payload = json.loads(path.read_text(encoding="utf-8"))
    recorded = payload.pop("canonical_outcome_sha256")
    observed = canonical_digest(payload)
    payload["canonical_outcome_sha256"] = recorded
    if recorded != observed or recorded != expected_spec_sha:
        raise AssertionError("immutable specification digest mismatch")
    matches = [system for system in payload["systems"] if tuple(system["bits"]) == pair]
    if len(matches) != 1:
        raise AssertionError("requested pair is absent or duplicated")
    system = dict(matches[0])
    system_sha = system.pop("system_sha256")
    if canonical_digest(system) != system_sha:
        raise AssertionError("individual system digest mismatch")
    system["system_sha256"] = system_sha
    return recorded, system


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    parser.add_argument("--spec-sha", required=True)
    parser.add_argument("--pair", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    pair = tuple(sorted(int(value) for value in args.pair.split(",")))
    if len(pair) != 2:
        raise SystemExit("pair must contain exactly two integers")
    spec_sha, system = load_system(Path(args.spec), pair, args.spec_sha)
    rank = int(system["effective_rank"])
    variable_count = rank + 1
    zero = (0,) * variable_count
    generators = [
        {(0,) + exponent: coefficient for exponent, coefficient in decode_polynomial(
            record["polynomial"], rank
        ).items()}
        for record in system["generators"]
    ]
    generators.append({(1,) + (1,) * rank: Fraction(1), zero: Fraction(-1)})
    started = time.perf_counter()
    representation, basis_size, processed, skipped = derive_identity(generators)
    elapsed = time.perf_counter() - started
    multipliers = [
        {"generator_index": index, "polynomial": encode_polynomial(polynomial)}
        for index, polynomial in enumerate(representation)
        if polynomial
    ]
    payload = {
        "schema": "torus-nullstellensatz-certificate-v1",
        "evidence_level": "exact rational polynomial identity",
        "spec_sha256": spec_sha,
        "system_sha256": system["system_sha256"],
        "pair": list(pair),
        "effective_rank": rank,
        "generator_count_including_saturation": len(generators),
        "basis_size_before_one": basis_size,
        "s_pairs_processed": processed,
        "coprime_s_pairs_skipped": skipped,
        "certificate_multiplier_count": len(multipliers),
        "certificate_term_count": sum(len(item["polynomial"]) for item in multipliers),
        "seconds": elapsed,
        "multipliers": multipliers,
        "identity": "sum(multiplier_i * generator_i) = 1",
    }
    payload["canonical_outcome_sha256"] = canonical_digest(payload)
    Path(args.output).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "pair": list(pair),
        "seconds": elapsed,
        "basis_size_before_one": basis_size,
        "certificate_term_count": payload["certificate_term_count"],
        "canonical_outcome_sha256": payload["canonical_outcome_sha256"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
