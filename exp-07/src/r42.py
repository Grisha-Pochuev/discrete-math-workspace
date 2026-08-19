#!/usr/bin/env python3
"""Exact symbolic certificate for the r42 power-deficit hierarchy.

The analytic determinant sign follows from the pointwise Cauchy-kernel
comparison.  This file checks the derivative exponents and the exact q=6
factorization.
"""
import sympy as sp

u,U,v,V=sp.symbols('u U v V', positive=True)
assert sp.factor((u+V)*(U+v)-(u+v)*(U+V)) == (U-u)*(V-v)

# Root-power functions on cube-value coordinates.
t=sp.symbols('t', positive=True)
for q in (1,2,4,5,6,7,8,9):
    alpha=sp.Rational(q,3)
    F=t**alpha
    F2=sp.factor(sp.diff(F,t,2))
    exponent=sp.factor(alpha-2)
    expected=sp.factor(alpha*(alpha-1)*t**exponent)
    assert sp.factor(F2-expected)==0
    print('q=',q,'exponent=',exponent,'F2=',F2)

# Exact q=6 mixed difference.  Let the cube-value rectangle be
# A, A+R / A+C, A+R+C.  Since root^6=(cube value)^2, the positive convex
# mixed difference is exactly 2*R*C.
A,R,C=sp.symbols('A R C')
D6=sp.expand(A**2+(A+R+C)**2-(A+R)**2-(A+C)**2)
assert sp.expand(D6-2*R*C)==0

# Power 1 and 2 match the existing integer measures d and 2m.
x,a,h,d=sp.symbols('x a h d')
y=x+h
z=x+a
w=x+a+h-d
D1=sp.expand(y+z-x-w)
D2=sp.expand(y**2+z**2-x**2-w**2)
assert sp.expand(D1-d)==0
m=sp.expand(D2/2)
assert sp.expand(m-(d*(x+a+h-d/sp.Integer(2))-a*h))==0

print('r42 power-deficit hierarchy certificate: PASS')
print('q=6 mixed deficit =',D6)
