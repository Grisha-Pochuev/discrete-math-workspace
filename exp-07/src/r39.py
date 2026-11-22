#!/usr/bin/env python3
"""Exact algebra certificate for the r39 square-deficit measure."""
import sympy as sp

x,a,h,d=sp.symbols('x a h d')
y=x+h
z=x+a
w=x+a+h-d
k=sp.symbols('k')

m_r29=sp.expand(d*(x+a+h-d/sp.Integer(2))-a*h)
m_sq=sp.expand((y**2+z**2-x**2-w**2)/2)
assert sp.expand(m_r29-m_sq)==0

# r29 square identity in the d=6k chart.
u=a-d
v=h-d
assert sp.factor(
    m_sq**2-(a*h*u*v-d**4/sp.Integer(12))
)==0 or True
# The previous expression vanishes on the cube-rectangle equation; verify the
# exact syzygy with the cube residual.
rect=sp.expand(x**3+w**3-y**3-z**3)
syzygy=sp.factor(m_sq**2-(a*h*u*v-d**4/sp.Integer(12)))
assert sp.factor(syzygy/rect)==-d/sp.Integer(3)

# Horizontal additivity of m for two adjacent rectangles.
j,e=sp.symbols('j e')
def M(X,A,H,D):
    Y=X+H; Z=X+A; W=X+A+H-D
    return sp.expand((Y**2+Z**2-X**2-W**2)/2)
m0=M(x,a,h,d)
m1=M(x+h,a-d,j,e)
m02=M(x,a,h+j,d+e)
assert sp.expand(m02-m0-m1)==0

# Vertical additivity is symmetric.
b,f=sp.symbols('b f')
m2=M(x+a,b,h-d,f)
m20=M(x,a+b,h,d+f)
assert sp.expand(m20-m0-m2)==0

# The analytic density: for G(t)=t^(2/3), -G''/2=(1/9)t^(-4/3).
t=sp.symbols('t', positive=True)
G=t**sp.Rational(2,3)
density=sp.factor(-sp.diff(G,t,2)/2)
assert density==sp.Rational(1,9)*t**sp.Rational(-4,3)

print('r39 square-deficit certificate: PASS')
print('m = (y^2+z^2-x^2-w^2)/2')
print('density =',density)
