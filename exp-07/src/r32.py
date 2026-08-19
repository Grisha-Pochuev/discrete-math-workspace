#!/usr/bin/env python3
"""Exact finite prime-power sharpening of r31.

The certificate works only with residue classes.  Translation of the additive
coordinate decomposition lets us set A0=0.  For each normalized A triple it
constructs exactly the B residues for which every A_i+B_j is a cube residue,
and measures the guaranteed p-adic valuation of the two Vandermonde products.
"""
from itertools import product


def vp(n, p):
    c = 0
    while n and n % p == 0:
        c += 1
        n //= p
    return c


def diff_vp_lower(r, s, p, k):
    """Lower bound for v_p(X-Y) from residues modulo p^k."""
    m = p**k
    d = (s-r) % m
    return k if d == 0 else vp(d, p)


def vandermonde_vp_lower(t, p, k):
    a,b,c = t
    return (
        diff_vp_lower(a,b,p,k)
        + diff_vp_lower(a,c,p,k)
        + diff_vp_lower(b,c,p,k)
    )


def exact_minimum(p, k):
    m = p**k
    cubes = {pow(x,3,m) for x in range(m)}
    best = None
    witness = None
    checked = 0

    # Translate A0 to zero and compensate in B; all sums and all coordinate
    # differences are unchanged.
    for a1 in range(m):
        for a2 in range(m):
            A = (0,a1,a2)
            allowed_B = [
                b for b in range(m)
                if b in cubes
                and (b+a1) % m in cubes
                and (b+a2) % m in cubes
            ]
            if not allowed_B:
                continue
            va = vandermonde_vp_lower(A,p,k)
            for B in product(allowed_B, repeat=3):
                checked += 1
                vb = vandermonde_vp_lower(B,p,k)
                total = va+vb
                if best is None or total < best:
                    best = total
                    witness = (A,B)

    assert best is not None and checked > 0
    return best, witness, len(cubes), checked


# The exact minima needed for the universal product.
cases = {
    (2,3): 6,   # modulo 8
    (3,3): 6,   # modulo 27
    (7,1): 2,   # modulo 7
    (13,1): 2,  # modulo 13
}

for (p,k), expected in cases.items():
    got, witness, ncubes, checked = exact_minimum(p,k)
    assert got == expected, (p,k,got,expected,witness)
    print(f'p={p} k={k} cubes={ncubes} checked={checked} min_vp={got} witness={witness}')

DIVISOR = 2**6 * 3**6 * 7**2 * 13**2
assert DIVISOR == 386358336
print('r32 prime-power modular certificate: PASS')
print('universal divisor =', DIVISOR)
