#!/usr/bin/env python3
"""Exact algebra certificate for the r50 genus-2 models and elliptic quotients."""
import sympy as sp

z,A,B,v=sp.symbols('z A B v', nonzero=True)

# Three rational genus-2 quotient models from r49.
H0=sp.expand((v**3-A-B)**2-4*A*B)
H1=sp.expand((B-v**3)**2+4*A*v**3)
H2=sp.expand((A-v**3)**2+4*B*v**3)
assert sp.expand(H0-(v**6-2*(A+B)*v**3+(A-B)**2))==0
assert sp.expand(H1-(v**6+2*(2*A-B)*v**3+B**2))==0
assert sp.expand(H2-(v**6+2*(2*B-A)*v**3+A**2))==0

# Birational quadratic eliminations from the trigonal models.
# H0: Y^3=z^2(z+A)(z+B), set v=Y/z.
# Then z^2+(A+B-v^3)z+AB=0.
w0=2*z+A+B-v**3
q0=z**2+(A+B-v**3)*z+A*B
assert sp.expand(w0**2-H0-4*q0)==0

# H1: Y^3=z(z+A)^2(z+B), set v=Y/(z+A).
w1=2*z+B-v**3
q1=z**2+(B-v**3)*z-A*v**3
assert sp.expand(w1**2-H1-4*q1)==0

# H2: Y^3=z(z+A)(z+B)^2, set v=Y/(z+B).
w2=2*z+A-v**3
q2=z**2+(A-v**3)*z-B*v**3
assert sp.expand(w2**2-H2-4*q2)==0

# Generic split model W^2=X^6+L X^3+s^6 over K=Q(s).
X,W,U,L,s=sp.symbols('X W U L s', nonzero=True)
poly=X**6+L*X**3+s**6
# Extra involution tau: X -> s^2/X, W -> s^3 W/X^3.
Xt=s**2/X
Wt=s**3*W/X**3
assert sp.factor((Wt**2-poly.subs(X,Xt))/(W**2-poly))==s**6/X**6

# U=X+s^2/X is tau-invariant.
Ut=sp.factor(Xt+s**2/Xt)
assert sp.factor(Ut-(X+s**2/X))==0

# For the + quotient, an invariant before cancelling the forced square is
# W*(X^3+s^3)/X^3.
h=U**3-3*s**2*U
assert sp.factor(h+2*s**3)==(U-s)**2*(U+2*s)
assert sp.factor(h-2*s**3)==(U+s)**2*(U-2*s)

Eplus=sp.expand((U+2*s)*(U**3-3*s**2*U+L))
Eminus=sp.expand((U-2*s)*(U**3-3*s**2*U+L))
print('r50 explicit genus-2 splitting certificate: PASS')
print('H0 = W^2 -',H0)
print('H1 = W^2 -',H1)
print('H2 = W^2 -',H2)
print('E+ : V^2 =',sp.factor(Eplus))
print('E- : V^2 =',sp.factor(Eminus))
