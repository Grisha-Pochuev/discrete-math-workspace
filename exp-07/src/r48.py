#!/usr/bin/env python3
"""Exact algebra certificate for the r48 fixed-layer closure curve.

This file checks the elementary algebraic identities.  Smoothness and genus
are proved in the accompanying report by the projective Jacobian criterion and
the complete-intersection adjunction formula.
"""
import sympy as sp

P,Q,R,T,A,B=sp.symbols('P Q R T A B')
F1=sp.expand(Q**3-P**3-A*T**3)
F2=sp.expand(R**3-P**3-B*T**3)

# The third obvious difference quotient.
assert sp.expand(F2-F1-(R**3-Q**3-(B-A)*T**3))==0

# Eliminate T: this is the fourth plane cubic quotient.
Fcross=sp.expand(B*Q**3-A*R**3+(A-B)*P**3)
assert sp.expand(B*F1-A*F2-Fcross)==0

# Map a difference cubic y^3-x^3=D to its j=0 Mordell model.
x,y,D=sp.symbols('x y D')
s=y-x
X=sp.factor(12*D/s)
Y=sp.factor(36*D*(y+x)/s)
M=sp.factor(Y**2-X**3+432*D**2)
# The Mordell residual vanishes identically on D=y^3-x^3.
assert sp.factor(M.subs(D,y**3-x**3))==0

# Inverse map on the affine chart X != 0.
XX,YY=sp.symbols('XX YY')
xinv=sp.factor((YY-36*D)/(6*XX))
yinv=sp.factor((YY+36*D)/(6*XX))
assert sp.factor(yinv-xinv-12*D/XX)==0
assert sp.factor((yinv**3-xinv**3-D).subs(YY**2,XX**3-432*D**2))==0

# A concrete base triple a<b<c supplies the rational point [a:b:c:1].
a,b,c=sp.symbols('a b c')
AA=b**3-a**3
BB=c**3-a**3
assert sp.expand(F1.subs({P:a,Q:b,R:c,T:1,A:AA,B:BB}))==0
assert sp.expand(F2.subs({P:a,Q:b,R:c,T:1,A:AA,B:BB}))==0
assert sp.expand(Fcross.subs({P:a,Q:b,R:c,A:AA,B:BB}))==0

print('r48 fixed-layer algebra certificate: PASS')
print('closure curve: Q^3-P^3=A*T^3, R^3-P^3=B*T^3')
print('fourth elliptic quotient:',Fcross,'= 0')
print('difference Mordell model: Y^2=X^3-432 D^2')
