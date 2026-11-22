#!/usr/bin/env python3
"""Exact invariant calculation for the two variable elliptic factors in r51."""
import sympy as sp

u,c,lam=sp.symbols('u c lam')

fplus=sp.expand((u+2)*(u**3-3*u-c))
fminus=sp.expand((u-2)*(u**3-3*u-c))

def invariants(f):
    a,b,cc,d,e=sp.Poly(f,u).all_coeffs()
    I=sp.factor(12*a*e-3*b*d+cc**2)
    J=sp.factor(72*a*cc*e+9*b*cc*d-27*a*d**2-27*b**2*e-2*cc**3)
    DeltaI=sp.factor(4*I**3-J**2)
    j=sp.factor(6912*I**3/DeltaI)
    return I,J,DeltaI,j

Ip,Jp,Dp,jp=invariants(fplus)
Im,Jm,Dm,jm=invariants(fminus)
assert Ip==-9*(2*c-5)
assert Jp==-27*(c**2-14*c+22)
assert Dp==-729*(c-2)*(c+2)**3
assert Im==9*(2*c+5)
assert Jm==-27*(c**2+14*c+22)
assert Dm==-729*(c-2)**3*(c+2)

c_lam=2*(lam+1)/(lam-1)
jp_lam=sp.factor(jp.subs(c,c_lam))
jm_lam=sp.factor(jm.subs(c,c_lam))
assert jp_lam==-27*(lam-9)**3*(lam-1)/lam**3
assert jm_lam==-27*(lam-1)*(9*lam-1)**3/lam
assert sp.factor(jp_lam.subs(lam,1/lam)-jm_lam)==0

print('r51 elliptic j-type certificate: PASS')
print('j_plus =',jp_lam)
print('j_minus =',jm_lam)
