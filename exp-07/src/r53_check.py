#!/usr/bin/env python3
import sympy as s

x,y,z,w,t=s.symbols('x y z w t')
R=(y+z-x-w)/2
C=(x+y+z+w)/2
P=(-x-y+z+w)/2
Q=(-x+y-z+w)/2
m=(y*y+z*z-x*x-w*w)/2
F=s.expand((x+t)**3+(w+t)**3-(y+t)**3-(z+t)**3)
rel=x**3+w**3-y**3-z**3
assert s.factor(F+6*t*(R*t+m)) == rel
assert s.factor(m-(R*C-P*Q)) == 0
Cp=2*P*Q/R-C
assert s.factor(Cp-C+2*m/R) == 0

def data(a,b,c,d):
    RR=(b+c-a-d)//2
    mm=(b*b+c*c-a*a-d*d)//2
    assert RR>0
    return RR,mm

RR,mm=data(9,16,33,34)
assert (RR,mm,mm//RR)==(3,54,18)
mu=mm//RR
X,Y,Z,W=mu-16,mu-9,33-mu,34-mu
assert (X,Y,Z,W)==(2,9,15,16)
assert X**3+W**3==Y**3+Z**3

RR,mm=data(1,9,10,12)
assert (RR,mm,mm//RR)==(3,18,6)
assert mm//RR < 9

print('r53 translation/Vieta certificate: PASS')
