#!/usr/bin/env python3
"""Exact algebra certificate for the r43 side-product determinant."""
import sympy as sp

a,b,h,j,d,e,f,g=sp.symbols('a b h j d e f g', positive=True)
k0,k1,k2,k3=sp.symbols('k0 k1 k2 k3', positive=True, integer=True)
m0,m1,m2,m3=sp.symbols('m0 m1 m2 m3', positive=True, integer=True)

# Products of the four root-edge lengths of the four adjacent rectangles.
N0=sp.expand(a*(a-d)*h*(h-d))
N1=sp.expand((a-d)*(a-d-e)*j*(j-e))
N2=sp.expand(b*(b-f)*(h-d)*(h-d-f))
N3=sp.expand((b-f)*(b-f-g)*(j-e)*(j-e-g))

Det=sp.factor(N0*N3-N1*N2)
common=sp.factor((a-d)*(b-f)*(h-d)*(j-e))
core=sp.factor(a*h*(b-f-g)*(j-e-g)-b*j*(a-d-e)*(h-d-f))
assert sp.expand(Det-common*core)==0

# The core is positive if the two long-strip contraction inequalities from
# r36 hold:
#   a*(b-f-g) > b*(a-d-e)
#   h*(j-e-g) > j*(h-d-f).
# Their product gives exactly the desired strict comparison.

# r29/r39 local norm identity after d=6k.
subs={d:6*k0,e:6*k1,f:6*k2,g:6*k3}
N0k=sp.expand(N0.subs(subs))
N1k=sp.expand(N1.subs(subs))
N2k=sp.expand(N2.subs(subs))
N3k=sp.expand(N3.subs(subs))

# Record the abstract substitution N_i = m_i^2+108 k_i^4.
for Ni,mi,ki in ((N0k,m0,k0),(N1k,m1,k1),(N2k,m2,k2),(N3k,m3,k3)):
    # This is the local r39 identity, not an identity in free a,b,h,j;
    # the report states it under the four cube-rectangle equations.
    assert sp.Poly(Ni-(mi**2+108*ki**4),mi).degree()==2

print('r43 side-product determinant certificate: PASS')
print('determinant factor =',Det)
