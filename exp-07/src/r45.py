#!/usr/bin/env python3
"""Exact algebra certificate for the r45 symmetric Markoff-grid reduction."""
import sympy as sp

x,a,b,h,j=sp.symbols('x a b h j')
k0,k1,k2,k3=sp.symbols('k0 k1 k2 k3')


def local(X,A,H,K):
    C=sp.expand(2*X+A+H-3*K)
    P=sp.expand(A-3*K)
    Q=sp.expand(H-3*K)
    y=X+H
    z=X+A
    w=X+A+H-6*K
    rect=sp.expand(X**3+w**3-y**3-z**3)
    mark=sp.expand(2*C*P*Q-3*K*(C**2+P**2+Q**2+3*K**2))
    m=sp.expand((y**2+z**2-X**2-w**2)/2)
    assert sp.expand(rect-sp.Rational(3,2)*mark)==0
    assert sp.expand(m-(3*K*C-P*Q))==0
    assert sp.expand((P**2-9*K**2)-A*(A-6*K))==0
    assert sp.expand((Q**2-9*K**2)-H*(H-6*K))==0
    return C,P,Q,m

C0,P0,Q0,m0=local(x,a,h,k0)
C1,P1,Q1,m1=local(x+h,a-6*k0,j,k1)
C2,P2,Q2,m2=local(x+a,b,h-6*k0,k2)
C3,P3,Q3,m3=local(x+a+h-6*k0,b-6*k2,j-6*k1,k3)

# Linear gluing of the four Markoff tiles.
assert sp.expand(P1-(P0-3*(k0+k1)))==0
assert sp.expand(P3-(P2-3*(k2+k3)))==0
assert sp.expand(Q2-(Q0-3*(k0+k2)))==0
assert sp.expand(Q3-(Q1-3*(k1+k3)))==0

assert sp.expand(C1-(C0+Q0+Q1))==0
assert sp.expand(C2-(C0+P0+P2))==0
assert sp.expand(C3-(C1+P1+P3))==0
assert sp.expand(C3-(C2+Q2+Q3))==0

print('r45 symmetric Markoff-grid certificate: PASS')
print('local equation: 2*C*P*Q = 3*k*(C^2+P^2+Q^2+3*k^2)')
print('local m: m = 3*k*C-P*Q')
