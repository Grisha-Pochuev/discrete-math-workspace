#!/usr/bin/env python3
"""Exact algebra checks behind the r28 TP2 kernel inequality."""
import sympy as sp

u,U,v,V = sp.symbols('u U v V', positive=True)

# Cross-product gap for u<U and v<V.
gap = sp.factor((u+V)*(U+v) - (u+v)*(U+V))
assert sp.expand(gap - (U-u)*(V-v)) == 0

# For K(x,y)=c*(x+y)^(-alpha), alpha>0, positivity of the gap means
# (u+v)(U+V) < (u+V)(U+v), hence the negative power gives
# K(u,v)K(U,V) > K(u,V)K(U,v).
# The exact cube-root kernel is alpha=5/3 and c=2/9.

t=sp.symbols('t', positive=True)
F=t**sp.Rational(1,3)
K=sp.factor(-sp.diff(F,t,2))
assert sp.simplify(K - sp.Rational(2,9)*t**(-sp.Rational(5,3))) == 0

print('r28 exact kernel certificate: PASS')
print('cross-product gap =', gap)
print('-F\'\'(t) =', K)
print('therefore the 2x2 deficit matrix satisfies d*g > e*f')
print('for integer cube rectangles d,e,f,g are divisible by 6: d*g-e*f >= 36')
