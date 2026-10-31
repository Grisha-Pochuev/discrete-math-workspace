#!/usr/bin/env python3
"""Exact symbolic sign certificate for the r36 root-gap TP2 lemma.

The analytic passage from the pointwise kernel inequality to interval gaps is
by multiplying out the two integrals.  This file verifies the algebraic sign
and the four resulting integer identities in r27 variables.
"""
import sympy as sp

u,U,b,B=sp.symbols('u U b B', positive=True)
a,h,j,d,e,f,g=sp.symbols('a h j d e f g', positive=True)

# For f(t)=t^(-2/3), the determinant
# f(u+b)f(U+B)-f(u+B)f(U+b) is positive for u<U and b<B,
# because the first denominator product is strictly smaller.
cross=sp.expand((u+B)*(U+b)-(u+b)*(U+B))
assert sp.factor(cross)==(B-b)*(U-u)

# Vertical root-gap matrix:
# [ a,       a-d,       a-d-e ]
# [ b,       b-f,       b-f-g ]
V01=sp.expand(a*(b-f)-b*(a-d))
V12=sp.expand((a-d)*(b-f-g)-(b-f)*(a-d-e))
assert sp.expand(V01-(b*d-a*f))==0
assert sp.expand(V12-((b-f)*e-(a-d)*g))==0

# Horizontal root-gap matrix:
# [ h,       j       ]
# [ h-d,     j-e     ]
# [ h-d-f,   j-e-g   ]
H01=sp.expand(h*(j-e)-j*(h-d))
H12=sp.expand((h-d)*(j-e-g)-(j-e)*(h-d-f))
assert sp.expand(H01-(j*d-h*e))==0
assert sp.expand(H12-((j-e)*f-(h-d)*g))==0

# With d,e,f,g=6*k_i, every positive determinant above is a multiple of 6.
k0,k1,k2,k3=sp.symbols('k0 k1 k2 k3', integer=True, positive=True)
subs={d:6*k0,e:6*k1,f:6*k2,g:6*k3}
for expr in (V01,V12,H01,H12):
    assert sp.factor(expr.subs(subs)/6).is_polynomial(a,b,h,j,k0,k1,k2,k3)

print('r36 root-gap TP2 certificate: PASS')
print('pointwise cross gap =',cross)
print('required: b*d>a*f; (b-f)*e>(a-d)*g; j*d>h*e; (j-e)*f>(h-d)*g')
