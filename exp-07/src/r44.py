#!/usr/bin/env python3
"""Exact algebra certificate for the r44 opposite-pair parameterization."""
import sympy as sp

s,d,m,p,q=sp.symbols('s d m p q')
t=s+d

# Pair A=(x,w) has sum s and product p.
# Pair B=(y,z) has sum t and product q.
# Half the square-power deficit is m.
square_eq=sp.expand((t**2-2*q)-(s**2-2*p)-2*m)
cube_eq=sp.expand((t**3-3*q*t)-(s**3-3*p*s))

sol=sp.solve([square_eq,cube_eq],[p,q],dict=True)[0]
pf=sp.factor(sol[p]);qf=sp.factor(sol[q])
assert pf==sp.factor(-(d**3+3*d**2*s-6*d*m-6*m*s)/(6*d))
assert qf==sp.factor((2*d**3+3*d**2*s+6*m*s)/(6*d))

D0=sp.factor(s**2-4*pf)
D1=sp.factor(t**2-4*qf)
assert sp.factor(D0-(s**2+2*d*s+sp.Rational(2,3)*d**2-4*m-4*m*s/d))==0
assert sp.factor(D1-(s**2-sp.Rational(1,3)*d**2-4*m*s/d))==0
assert sp.factor(D0-D1-(d**2+2*d*s-4*m))==0

# Converse replay: substituting the forced products kills both defining
# equations identically.
assert sp.factor(square_eq.subs({p:pf,q:qf}))==0
assert sp.factor(cube_eq.subs({p:pf,q:qf}))==0

print('r44 opposite-pair certificate: PASS')
print('xw =',pf)
print('yz =',qf)
print('(w-x)^2 =',D0)
print('(z-y)^2 =',D1)
