#!/usr/bin/env python3
"""Exact algebra certificate for the r37 contraction-norm lemma.

No appeal to a parametrization theorem is required: the norm relation is
factored directly from one equal-sum cube rectangle.
"""
import sympy as sp

r,s,L,gamma=sp.symbols('r s L gamma')

x=gamma*(r+L**2)
y=gamma*(L*r+1)
z=gamma*(s+L**2)
w=gamma*(L*s+1)

# The vertical outer and inner root gaps have ratio L.
A=sp.factor(z-x)
U=sp.factor(w-y)
assert sp.factor(U-L*A)==0

# The equal-sum cube equation factors by the Eisenstein norm relation.
E=sp.factor(x**3+w**3-y**3-z**3)
expected=-gamma**3*(L-1)*(r-s)*(L**2+L+1)*(r**2+r*s+s**2-3*L)
assert sp.expand(E-expected)==0

# Conversely, the norm relation forces the cube rectangle.
assert sp.factor(E.subs(L,(r**2+r*s+s**2)/3))==0

# Direct inverse chart from an arbitrary nondegenerate rectangle.  Put
# L=(w-y)/(z-x) and gamma=(y-L*x)/(1-L^3).  The common residual factor in
# the cube equation and the norm equation is checked symbolically.
X,Y,Z,L0=sp.symbols('X Y Z L0')
G=(Y-L0*X)/(1-L0**3)
R=sp.factor(X/G-L0**2)
S=sp.factor(Z/G-L0**2)
W=Y+L0*(Z-X)
F=sp.factor(L0**3*X**2-2*L0**3*X*Z+L0**3*Z**2-3*L0**2*X*Y+3*L0**2*Y*Z+3*L0*Y**2-X**2-X*Z-Z**2)
assert sp.factor(X**3+W**3-Y**3-Z**3 + (X-Z)*F)==0
norm_res=sp.factor(R**2+R*S+S**2-3*L0)
assert sp.factor(norm_res-(L0-1)*(L0**2+L0+1)*F/(L0*X-Y)**2)==0

print('r37 contraction-norm certificate: PASS')
print('cube residual factor =',sp.factor(E/gamma**3))
print('outer gap =',A,'inner gap =',U)
