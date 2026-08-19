#!/usr/bin/env python3
"""Exact symbolic certificate for the r29 divisor reduction.

This file is intentionally non-executable by the workflow.  It only records
exact identities refining the r27 root-grid equations.
"""
import sympy as sp

X,A,H,D = sp.symbols('X A H D')
K,N,U,V = sp.symbols('K N U V')

# One adjacent cube rectangle.
rect = sp.expand(
    X**3 + (X+A+H-D)**3 - (X+H)**3 - (X+A)**3
)

# Inner gaps after removing the mixed deficit.
inner_form = sp.expand(
    3*(A-D)*(H-D)*(2*X+A+H)
    - D*(3*X**2 + 3*D*X + D**2)
)
assert sp.expand(rect - inner_form) == 0

# r27 gives D == 0 (mod 6).  Put D=6K, write the positive inner gaps as
# U=A-D, V=H-D, and center the absolute root by N=X+D/2=X+3K.
sub = {
    D: 6*K,
    A: U + 6*K,
    H: V + 6*K,
    X: N - 3*K,
}

divisor_eq = sp.expand(
    U*V*(2*N + U + V + 6*K)
    - 6*K*(N**2 + 3*K**2)
)
# The original cube rectangle is exactly three times this equation.
assert sp.expand(rect.subs(sub) - 3*divisor_eq) == 0

# A second equivalent form is a quartic square.  Define
# M = 6*K*N-U*V.  On divisor_eq=0,
# M^2 = U*V*(U+6K)*(V+6K)-108*K^4.
M = 6*K*N - U*V
quartic = sp.expand(
    M**2 - (U*V*(U+6*K)*(V+6*K) - 108*K**4)
)
assert sp.factor(quartic / divisor_eq) == -6*K

# Full 3x3 compatibility.  Write d,e,f,g=6*k0,... and use u,v,p,q
# for the four inward root gaps around the adjacent rectangles.
x,u,v,p,q = sp.symbols('x u v p q')
k0,k1,k2,k3 = sp.symbols('k0 k1 k2 k3')

n0 = x + 3*k0
n1 = x + (v + 6*k0) + 3*k1
n2 = x + (u + 6*k0) + 3*k2
n3 = x + u + v + 6*k0 + 3*k3

assert sp.expand(n1 - (n0 + v + 3*(k0+k1))) == 0
assert sp.expand(n2 - (n0 + u + 3*(k0+k2))) == 0
assert sp.expand(n3 - (n0 + u + v + 3*(k0+k3))) == 0
assert sp.expand(n3 + n0 - n1 - n2 - 3*(k3-k0-k1-k2)) == 0

# r28 rescales to a primitive determinant inequality in the k variables.
d,e,f,g = 6*k0,6*k1,6*k2,6*k3
assert sp.expand(d*g - e*f - 36*(k0*k3-k1*k2)) == 0

print('r29 exact divisor reduction certificate: PASS')
print('single tile: U*V*(2*N+U+V+6*K) = 6*K*(N^2+3*K^2)')
print('square form: (6*K*N-U*V)^2 = U*V*(U+6*K)*(V+6*K)-108*K^4')
print('r28 becomes k0*k3 > k1*k2, hence k0*k3-k1*k2 >= 1')
