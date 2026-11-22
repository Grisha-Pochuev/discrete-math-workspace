#!/usr/bin/env python3
"""Finite exact modular certificate for r31.

For m in {4,7,9,13}, exhaustively verify the modular statement used in
r31.md.  No floating point arithmetic and no external data are used.
"""

MODS = (4, 7, 9, 13)
EXPECTED = {
    4: {0, 1, 3},
    7: {0, 1, 6},
    9: {0, 1, 8},
    13: {0, 1, 5, 8, 12},
}

for m in MODS:
    cubes = {pow(x, 3, m) for x in range(m)}
    assert cubes == EXPECTED[m]

    # A nontrivial translate of the cube-residue set intersects it in at
    # most two residues.  This is the short combinatorial reason behind the
    # Vandermonde divisibility statement.
    for t in range(1, m):
        inter = cubes & {(c - t) % m for c in cubes}
        assert len(inter) <= 2

    # Exhaustive replay.  Translation lets us normalize A0=0.  If every
    # A_i+B_j is a cube residue, the product of the two 3-point Vandermonde
    # factors is divisible by m^2.
    checked = 0
    for a1 in range(m):
        for a2 in range(m):
            A = (0, a1, a2)
            VA = a1 * a2 * (a2 - a1)
            for b0 in range(m):
                for b1 in range(m):
                    for b2 in range(m):
                        B = (b0, b1, b2)
                        if not all((a + b) % m in cubes for a in A for b in B):
                            continue
                        checked += 1
                        VB = (b1-b0) * (b2-b0) * (b2-b1)
                        assert (VA * VB) % (m*m) == 0
    assert checked > 0
    print(f'm={m} checked={checked} PASS')

M = 4*7*9*13
assert M == 3276
assert M*M == 10732176
print('r31 modular Vandermonde certificate: PASS')
print('universal divisor = 10732176')
