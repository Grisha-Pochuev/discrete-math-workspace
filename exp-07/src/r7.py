#!/usr/bin/env python3
"""Exact one-parameter certificate for a universal-multiple subfamily.

The top triple is normalized to (1,r,r^2), r in Q, r>1.  For each edge
we use an integer multiple of its distinguished rational point on the
corresponding Fermat cubic.  The lower-row condition then becomes one
rational equation in r.  Rational roots are found exactly and every surviving
configuration is reconstructed and checked exactly.

No floating-point arithmetic is used for acceptance.
"""

import argparse
import json
import math
import time
from pathlib import Path

import sympy as sp

r = sp.symbols("r")
K = 1 + r**3
CURVE_B = -432 * K**2


def cancel(x):
    return sp.cancel(x)


# Fermat (1,r) -> Y^2 = X^3 - 432 K^2.
BASE = (
    cancel(12 * K / (1 + r)),
    cancel(36 * K * (1 - r) / (1 + r)),
)


def dbl(P):
    x, y = P
    lam = cancel(3 * x*x / (2*y))
    x3 = cancel(lam*lam - 2*x)
    y3 = cancel(lam*(x - x3) - y)
    return x3, y3


def add(P, Q):
    if P is None:
        return Q
    if Q is None:
        return P
    x1, y1 = P
    x2, y2 = Q
    dx = cancel(x2 - x1)
    if dx == 0:
        if cancel(y2 - y1) == 0:
            return dbl(P)
        raise ZeroDivisionError("symbolic inverse points")
    lam = cancel((y2 - y1) / dx)
    x3 = cancel(lam*lam - x1 - x2)
    y3 = cancel(lam*(x1 - x3) - y1)
    return x3, y3


def mul(P, n):
    assert n >= 1
    R = None
    Q = P
    while n:
        if n & 1:
            R = add(R, Q)
        n >>= 1
        if n:
            Q = dbl(Q)
    return R


def fermat_pair(P):
    X, Y = P
    u = cancel((36*K + Y) / (6*X))
    v = cancel((36*K - Y) / (6*X))
    assert cancel(u**3 + v**3 - K) == 0
    return u, v


def build_maps(min_m, max_m):
    pairs = {}
    diffs = {}
    degrees = {}
    for m in range(min_m, max_m + 1):
        Pm = mul(BASE, m)
        u, v = fermat_pair(Pm)
        d = cancel(v**3 - u**3)
        pairs[m] = (u, v)
        diffs[m] = d
        num, den = d.as_numer_denom()
        degrees[m] = [sp.Poly(num, r).degree(), sp.Poly(den, r).degree()]
    return pairs, diffs, degrees


def rational_roots(expr):
    """Return all rational roots of a rational expression, excluding poles."""
    num, den = sp.together(expr).as_numer_denom()
    poly = sp.Poly(num, r, domain=sp.QQ)
    roots = sp.polys.polytools.ground_roots(poly)
    out = []
    for q, mult in roots.items():
        q = sp.Rational(q)
        if den.subs(r, q) == 0:
            continue
        out.append((q, int(mult)))
    out.sort(key=lambda z: z[0])
    return out


def rat(x):
    x = cancel(x)
    if not x.is_Rational:
        raise ValueError(f"not rational: {x}")
    return sp.Rational(x)


def orient(pair, coeff):
    """Return row2,row3 so row2^3-row3^3 = coeff*(v^3-u^3)."""
    u, v = pair
    if coeff == 1:
        return v, u
    if coeff == -1:
        return u, v
    raise ValueError(coeff)


def clear_bases(vals):
    L = 1
    for x in vals:
        L = math.lcm(L, int(x.q))
    z = [int(x * L) for x in vals]
    g = 0
    for x in z:
        g = math.gcd(g, abs(x))
    if g > 1:
        z = [x // g for x in z]
    return z


def verify_candidate(root, m_ab, m_bc, m_ac, s_ab, s_bc, pairs, diffs):
    rr = sp.Rational(root)
    rr2 = rr*rr

    ab = tuple(rat(x.subs(r, rr)) for x in pairs[m_ab])
    # The BC edge is r times a copy of the same normalized edge.
    bc0 = tuple(rat(x.subs(r, rr)) for x in pairs[m_bc])
    bc = (rr*bc0[0], rr*bc0[1])
    ac = tuple(rat(x.subs(r, rr2)) for x in pairs[m_ac])

    if min(ab + bc + ac) <= 0:
        return None

    dab = rat(diffs[m_ab].subs(r, rr))
    dbc = rr**3 * rat(diffs[m_bc].subs(r, rr))
    dac = rat(diffs[m_ac].subs(r, rr2))
    if cancel(dac + s_ab*dab + s_bc*dbc) != 0:
        raise AssertionError("candidate does not satisfy exact difference relation")

    AB = orient(ab, s_ab)
    BC = orient(bc, s_bc)
    AC = orient(ac, 1)

    vals = [
        sp.Rational(1), rr, rr2,
        BC[0], AC[0], AB[0],
        BC[1], AC[1], AB[1],
    ]
    if min(vals) <= 0 or len(set(vals)) != 9:
        return None

    bases = clear_bases(vals)
    if min(bases) <= 0 or len(set(bases)) != 9:
        return None

    c = [x**3 for x in bases]
    sums = [
        c[0] + c[1] + c[2],
        c[3] + c[4] + c[5],
        c[6] + c[7] + c[8],
        c[0] + c[3] + c[6],
        c[1] + c[4] + c[7],
        c[2] + c[5] + c[8],
    ]
    if len(set(sums)) != 1:
        raise AssertionError("reconstruction failed six exact sums")

    return {
        "r": [int(rr.p), int(rr.q)],
        "multipliers": {"ab": m_ab, "bc": m_bc, "ac": m_ac},
        "signs": {"ab": s_ab, "bc": s_bc, "ac": 1},
        "bases": bases,
        "sum": str(sums[0]),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-m", type=int, default=3)
    ap.add_argument("--max-m", type=int, default=6)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    if args.min_m < 2 or args.max_m < args.min_m:
        raise SystemExit(2)

    t0 = time.time()
    pairs, diffs, degrees = build_maps(args.min_m, args.max_m)

    families = 0
    rational_roots_total = 0
    roots_gt1 = 0
    positive_exact_candidates = 0
    hits = []
    root_records = []

    for m_ab in range(args.min_m, args.max_m + 1):
        for m_bc in range(args.min_m, args.max_m + 1):
            for m_ac in range(args.min_m, args.max_m + 1):
                dac = diffs[m_ac].subs(r, r*r)
                for s_ab in (-1, 1):
                    for s_bc in (-1, 1):
                        families += 1
                        expr = dac + s_ab*diffs[m_ab] + s_bc*r**3*diffs[m_bc]
                        roots = rational_roots(expr)
                        rational_roots_total += sum(mult for _, mult in roots)
                        for root, mult in roots:
                            if root <= 1:
                                continue
                            roots_gt1 += mult
                            rec = {
                                "r": [int(root.p), int(root.q)],
                                "multipliers": [m_ab, m_bc, m_ac],
                                "signs": [s_ab, s_bc, 1],
                                "multiplicity": mult,
                            }
                            root_records.append(rec)
                            hit = verify_candidate(
                                root, m_ab, m_bc, m_ac, s_ab, s_bc, pairs, diffs
                            )
                            if hit is not None:
                                positive_exact_candidates += 1
                                hits.append(hit)

    # De-duplicate identical reconstructed squares while preserving evidence.
    unique = {}
    for h in hits:
        unique.setdefault(tuple(h["bases"]), h)
    hits = list(unique.values())

    result = {
        "schema_version": 1,
        "scope": {
            "top": "(1,r,r^2), rational r>1",
            "min_multiplier": args.min_m,
            "max_multiplier": args.max_m,
            "sign_normalization": "AC coefficient fixed to +1",
        },
        "map_difference_degrees": {str(k): v for k, v in degrees.items()},
        "families": families,
        "rational_roots_total_with_multiplicity": rational_roots_total,
        "rational_roots_gt1_with_multiplicity": roots_gt1,
        "positive_distinct_exact_candidates": positive_exact_candidates,
        "unique_hits": len(hits),
        "root_records_gt1": root_records,
        "hits": hits,
        "elapsed_seconds": time.time() - t0,
    }
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        "R7_SUMMARY"
        f" families={families}"
        f" roots_gt1={roots_gt1}"
        f" exact_candidates={positive_exact_candidates}"
        f" hits={len(hits)}"
    )


if __name__ == "__main__":
    main()
