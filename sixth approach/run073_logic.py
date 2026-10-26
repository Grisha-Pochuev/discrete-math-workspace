#!/usr/bin/env python3
"""Shared CP-SAT primitives for the exact factored two-row encoding."""

from __future__ import annotations


def add_exact_cardinality_indicator(model, literals, fixed_count, target, name):
    """Return b with b iff fixed_count + sum(literals) == target."""
    indicator = model.NewBoolVar(name)
    expression = fixed_count + sum(literals)
    model.Add(expression == target).OnlyEnforceIf(indicator)
    model.Add(expression != target).OnlyEnforceIf(indicator.Not())
    return indicator


def add_pair_to_group_implication(model, cardinality_indicator, left, right, group_indicator):
    """Encode cardinality & left & right -> group; None denotes constant true."""
    clause = [cardinality_indicator.Not(), group_indicator]
    if left is not None:
        clause.append(left.Not())
    if right is not None:
        clause.append(right.Not())
    model.AddBoolOr(clause)


def add_group_conflict(model, binomial_group, trinomial_group):
    model.AddBoolOr([binomial_group.Not(), trinomial_group.Not()])
