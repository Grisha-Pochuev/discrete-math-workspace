#!/usr/bin/env python3
"""Exact algebra and Riemann-Hurwitz bookkeeping for r49."""
import sympy as sp

P,Q,R,A,B,z=sp.symbols('P Q R A B z')
subs={P**3:z,Q**3:z+A,R**3:z+B}

patterns={
    'E_PQ':(1,1,0),
    'E_PR':(1,0,1),
    'E_QR':(0,1,1),
    'E_PQR':(1,1,1),
    'H_P2QR':(2,1,1),
    'H_PQ2R':(1,2,1),
    'H_PQR2':(1,1,2),
}

def rhs(e):
    i,j,k=e
    return sp.expand(z**i*(z+A)**j*(z+B)**k)

def genus(e):
    finite=sum(int(v%3!=0) for v in e)
    infinity=int(sum(e)%3!=0)
    r=finite+infinity
    # Degree-3 cyclic cover with full ramification at r points:
    # 2g-2 = -6 + 2r.
    return r-2,r

# Exact monomial quotient identities.
for name,e in patterns.items():
    i,j,k=e
    Y=P**i*Q**j*R**k
    lhs=sp.expand(Y**3)
    # Replace cubes by z,z+A,z+B.
    reduced=lhs.xreplace({P**3:z,Q**3:z+A,R**3:z+B})
    # xreplace catches exact powers after expansion poorly for powers 6, so use subs.
    reduced=sp.expand(lhs.subs({P**3:z,Q**3:z+A,R**3:z+B}, simultaneous=True))
    assert sp.expand(reduced-rhs(e))==0,(name,reduced,rhs(e))
    g,r=genus(e)
    expected=1 if name.startswith('E_') else 2
    assert g==expected,(name,g,r)
    print(name,e,'genus',g,'branch_points',r,'rhs',rhs(e))

assert sum(genus(e)[0] for e in patterns.values())==10

# The fourth elliptic quotient is equivalent to eliminating z/T from the
# three-coordinate model: B Q^3-A R^3+(A-B)P^3=0.
Fcross=sp.expand(B*Q**3-A*R**3+(A-B)*P**3)
assert sp.expand(Fcross.subs({Q**3:P**3+A,R**3:P**3+B}, simultaneous=True))==0

print('r49 quotient tower certificate: PASS')
print('total quotient genus = 10')
