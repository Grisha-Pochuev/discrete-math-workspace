#!/usr/bin/env python3
"""Exact symbolic certificate for the two-shift gap-ratio lemma.

For a base cube x^3 and positive root increments h<k, write t=x/h and
lambda=k/h.  If D=(x+h)^3-x^3 and E=(x+k)^3-x^3, then E/D is the rational
function R(t,lambda) below.  The factorizations certified here imply the
monotonicity statements recorded in reports/r21.md.
"""
import sympy as sp

t, lam = sp.symbols("t lam", positive=True)
F = 3*t**2 + 3*t + 1
G = 3*t**2 + 3*lam*t + lam**2
R = sp.factor(lam * G / F)

# Exact normalisation of the two cube differences.
x, h, k = sp.symbols("x h k", positive=True)
D = sp.expand((x+h)**3 - x**3)
E = sp.expand((x+k)**3 - x**3)
assert sp.expand(D - h*(3*x**2 + 3*x*h + h**2)) == 0
assert sp.expand(E - k*(3*x**2 + 3*x*k + k**2)) == 0
assert sp.factor((E/D).subs({x:t*h, k:lam*h}) - R) == 0

# For lambda>1, R decreases strictly with t and increases strictly with lambda.
dt = sp.factor(sp.diff(R, t))
dl = sp.factor(sp.diff(R, lam))
dt_expected = -3*lam*(lam-1)*(3*t**2 + 2*t + 2*lam*t + lam) / F**2
dl_expected = 3*(lam+t)**2 / F
assert sp.factor(dt - dt_expected) == 0
assert sp.factor(dl - dl_expected) == 0

# Useful sharp interval: lambda < E/D < lambda^3 for x,h>0 and lambda>1.
lo = sp.factor(R-lam)
hi = sp.factor(lam**3-R)
lo_expected = lam*(lam-1)*(lam + 3*t + 1)/F
hi_expected = 3*lam*t*(lam-1)*(lam*t + lam + t)/F
assert sp.factor(lo-lo_expected) == 0
assert sp.factor(hi-hi_expected) == 0

# The first-shift normalized factor is strictly increasing in both positive
# variables before normalisation: D=h(3x^2+3xh+h^2).
Dx = sp.factor(sp.diff(h*(3*x**2+3*x*h+h**2), x))
Dh = sp.factor(sp.diff(h*(3*x**2+3*x*h+h**2), h))
assert Dx == 3*h*(h+2*x)
assert Dh == 3*(h+x)**2

print("r21 exact certificate: PASS")
print("R(t,lambda) =", R)
print("dR/dt =", dt)
print("dR/dlambda =", dl)
print("R-lambda =", lo)
print("lambda^3-R =", hi)
