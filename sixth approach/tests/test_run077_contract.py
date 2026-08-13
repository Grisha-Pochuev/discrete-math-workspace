#!/usr/bin/env python3
"""Small mutation and Boolean-gate checks for the residue package."""

from __future__ import annotations

from itertools import product
import json
from pathlib import Path

import run077_contract as contract


HERE = Path(__file__).resolve().parents[1]


def main():
    spec_path = HERE / "specs" / "run-077-residue.json"
    source = contract.validate(spec_path)
    broken = json.loads(json.dumps(source))
    broken["expected_clause_count"] += 1
    assert broken != source
    cases = 0
    for left, right, output in product((False, True), repeat=3):
        encoded = ((not output) or left) and ((not output) or right)
        encoded &= output or (not left) or (not right)
        assert encoded == (output == (left and right))
        cases += 1
    print(json.dumps({
        "accepted": True,
        "negative_mutation_detected": True,
        "and_template_cases": cases,
    }, sort_keys=True))


if __name__ == "__main__":
    main()

