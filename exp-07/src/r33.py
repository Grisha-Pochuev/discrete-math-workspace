#!/usr/bin/env python3
"""Exact finite mod-49 sharpening of the modular Vandermonde filter."""
from itertools import combinations_with_replacement

P=7
K=2
M=P**K
C={pow(x,3,M) for x in range(M)}
assert len(C)==15


def vp(n):
    c=0
    while n and n%P==0:
        c+=1;n//=P
    return c


def dv(a,b):
    d=(b-a)%M
    return K if d==0 else vp(d)


def vv(t):
    a,b,c=t
    return dv(a,b)+dv(a,c)+dv(b,c)

best=999
witness=None
checked=0

# Translate A0 to zero.  For each A triple, B entries must lie in the exact
# intersection C & (C-a1) & (C-a2).
for a1 in range(M):
    for a2 in range(M):
        A=(0,a1,a2)
        I=[b for b in range(M) if b in C and (b+a1)%M in C and (b+a2)%M in C]
        if not I:
            continue
        va=vv(A)
        for B in combinations_with_replacement(I,3):
            checked+=1
            total=va+vv(B)
            if total<best:
                best=total
                witness=(A,B)

assert best==4, (best,witness)
assert checked>0
print('r33 mod49 certificate: PASS')
print('cube_residues=',len(C),'checked=',checked,'min_v7=',best,'witness=',witness)

DIVISOR=2**6 * 3**6 * 7**4 * 13**2
assert DIVISOR==18931558464
print('sharpened universal divisor =',DIVISOR)
