#!/usr/bin/env python3
"""Exact algebra certificate for the r2 reduction.

This file is deliberately self-contained apart from SymPy.  Every asserted
identity is exact over Q; floating-point arithmetic is not used.
"""

import sympy as sp

u, a, b, t = sp.symbols("u a b t")
D1, D2, k1, k2, k3 = sp.symbols("D1 D2 k1 k2 k3")

P = 1 - u + 3*u**2
Q = 1 + u + 3*u**2
Y = 2*u + 3*u**3
C = 1 - Y
D = 1 + Y

# Base identity.
assert sp.expand(P**3 + Q**3 - C**3 - D**3) == 0

alpha = sp.factor(u / (1 + 3*u**2))
beta = Y
r = lambda x: sp.factor((1 - x) / (1 + x))
assert sp.factor(P/Q - r(alpha)) == 0
assert sp.factor(C/D - r(beta)) == 0

# Low-degree relation between the two relative half-differences.
F = 9*a**3*b**2 + 3*a**3 + 3*a**2*b + 2*a - b
assert sp.factor(sp.together(F.subs({a: alpha, b: beta}))) == 0

# Birational recovery of the original parameter on F=0.
u_inv = sp.factor(a*(1 + 3*a*b) / (1 + 3*a**2))
num_a = sp.factor(sp.together(a - alpha.subs(u, u_inv)).as_numer_denom()[0])
num_b = sp.factor(sp.together(b - beta.subs(u, u_inv)).as_numer_denom()[0])
assert sp.factor(num_a / (3*a**2*F)) == 1
assert sp.factor(num_b / (-(9*a**3*b + 6*a**2 + 1)*F)) == 1

disc = sp.factor(sp.discriminant(F, b))
assert sp.expand(disc - (1 + 3*a**2)**2*(1 - 12*a**2)) == 0

# A rational parametrization; t=u/2.
a_t = sp.factor(2*t / (1 + 12*t**2))
b_t = sp.factor(4*t + 24*t**3)
assert sp.factor(F.subs({a: a_t, b: b_t})) == 0

# Ratio multiplication in relative half-difference coordinates.
x, y, z = sp.symbols("x y z")
compose = sp.factor((x + y) / (1 + x*y))
assert sp.factor(r(x)*r(y) - r(compose)) == 0

# Difference/sum ratio for a centered pair 1±z.
theta = lambda q: sp.factor(q*(3 + q**2) / (1 + 3*q**2))
assert sp.factor(
    ((1 + z)**3 - (1 - z)**3) / ((1 + z)**3 + (1 - z)**3) - theta(z)
) == 0

# Multiplicative change of the pair difference under the alternate
# representation.  It is strictly >1 on the physical branch.
k = sp.factor(theta(beta) / theta(alpha))
k_expected = sp.factor(
    (3*u**2 + 2)*(9*u**6 + 12*u**4 + 4*u**2 + 3)
    / (27*u**4 + 19*u**2 + 3)
)
assert sp.factor(k - k_expected) == 0
km1_num, km1_den = sp.together(k - 1).as_numer_denom()
km1_num = sp.factor(km1_num)
km1_den = sp.factor(km1_den)
assert km1_num == (
    (3*u**2 - 3*u + 1)
    * (3*u**2 + 3*u + 1)
    * (3*u**4 + 7*u**2 + 3)
)
assert km1_den == 27*u**4 + 19*u**2 + 3
assert sp.discriminant(3*u**2 - 3*u + 1, u) == -3
assert sp.discriminant(3*u**2 + 3*u + 1, u) == -3

# beta>alpha for u>0.
assert sp.factor(beta - alpha) == u*(9*u**4 + 9*u**2 + 1)/(3*u**2 + 1)

# Normalized alternative differences and top ratios.
fA = sp.factor((D**3 - C**3) / Q**3)
fB = sp.factor((Q**3 - P**3) / D**3)
rA = sp.factor(P/Q)
rB = sp.factor(C/D)

# ABA exclusion.
# If x=-log(rA(u)), then exp(3x)*(fA-1) collapses to a simple expression.
TA = sp.factor((Q/P)**3 * (fA - 1))
assert sp.factor(TA - (1 - 2*(C/P)**3)) == 0

# On C>0, necessarily 0<u<1/2.  There rA is strictly decreasing and C/P
# is strictly decreasing.  The positivity decompositions below are exact.
rA_num = sp.factor(sp.together(sp.diff(rA, u)).as_numer_denom()[0])
assert sp.expand(rA_num - 2*(3*u**2 - 1)) == 0
cp_num = sp.factor(sp.together(sp.diff(C/P, u)).as_numer_denom()[0])
cp_pos = 9*u**4 - 6*u**3 + 3*u**2 + 6*u + 1
assert sp.expand(cp_num + cp_pos) == 0
assert sp.expand(cp_pos - (3*u**2*(3*u**2 - 2*u + 1) + 6*u + 1)) == 0
assert sp.discriminant(3*u**2 - 2*u + 1, u) == -8

# For B the alternative normalized difference is strictly smaller than the
# top normalized difference.
b_gap = sp.factor(1 - rB**3 - fB)
assert sp.factor(b_gap - 2*(P**3 - C**3)/D**3) == 0
assert sp.factor(P - C) == u*(3*u**2 + 3*u + 1)

# Consequently, for any ABA ratio triangle rA(w)=rA(u)rB(v), w>u and
# monotonicity of TA gives
#   fA(w)-rB(v)^3 fA(u) > 1-rB(v)^3 > fB(v),
# so exact cancellation is impossible.

# Two additional sign certificates using only k_i>1 and D1,D2>0.
# BBA: the two inner alternatives shrink and the outer one expands.
bba_gap = sp.factor(k3*(D1 + D2) - D1/k1 - D2/k2)
bba_positive = (k3 - 1)*(D1 + D2) + (1 - 1/k1)*D1 + (1 - 1/k2)*D2
assert sp.factor(bba_gap - bba_positive) == 0

# AAB: the outer alternative cannot be the largest-equals-sum branch.
aab_gap = sp.factor(k1*D1 + k2*D2 - (D1 + D2)/k3)
aab_positive = (k1 - 1)*D1 + (k2 - 1)*D2 + (1 - 1/k3)*(D1 + D2)
assert sp.factor(aab_gap - aab_positive) == 0

print("r2 exact certificate: PASS")
print("low-degree relation:", F)
print("inverse u:", u_inv)
print("k(u)-1 numerator:", km1_num)
print("ABA: excluded by exact monotonicity certificate")
print("BBA: excluded by exact sign certificate")
print("AAB: outer-largest branch excluded")
