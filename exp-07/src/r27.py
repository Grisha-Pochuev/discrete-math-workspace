#!/usr/bin/env python3
"""Exact algebra certificate for the root-grid reduction.

No floating point arithmetic is used. The file verifies the generic 2x2
rectangle equation, its quadratic discriminant, and the four-rectangle
reconstruction of a Cartesian additive 3x3 cube grid.
"""
import sympy as sp

x,a,b,h,j,d,e,f,g = sp.symbols('x a b h j d e f g')


def Q(X,A,H,D):
    S = X + A + H
    return sp.expand(D*(3*S**2 - 3*D*S + D**2) - 3*A*H*(2*X + A + H))


def rect(X,A,H,D):
    return sp.expand(X**3 + (X+A+H-D)**3 - (X+H)**3 - (X+A)**3)

# One 2x2 rectangle is equivalent to Q=0.
assert sp.expand(rect(x,a,h,d) + Q(x,a,h,d)) == 0

# Q is quadratic in the absolute lower root x.
P = sp.Poly(Q(x,a,h,d), x)
assert P.degree() == 2
assert P.LC() == 3*d

# Exact discriminant factorization.
Delta = sp.factor(sp.discriminant(P))
Delta_expected = sp.factor(3*(12*a*h*(a-d)*(h-d) - d**4))
assert sp.expand(Delta - Delta_expected) == 0

# For integer roots, cube equality modulo 3 gives d == 0 mod 3 because
# n^3 == n (mod 3) and d=(x+h)+(x+a)-x-(x+a+h-d).
y=x+h
z=x+a
w=x+a+h-d
assert sp.expand(y+z-x-w-d) == 0

# Parameterize all nine roots by first-row gaps h,j, first-column gaps a,b,
# and the four positive mixed deficits d,e,f,g.
r00=x
r01=x+h
r02=x+h+j
r10=x+a
r11=x+a+h-d
r12=x+a+h+j-d-e
r20=x+a+b
r21=x+a+b+h-d-f
r22=x+a+b+h+j-d-e-f-g
R=[[r00,r01,r02],[r10,r11,r12],[r20,r21,r22]]

Q00=Q(x,a,h,d)
Q01=Q(x+h,a-d,j,e)
Q10=Q(x+a,b,h-d,f)
Q11=Q(x+a+h-d,b-f,j-e,g)
rects=[
    sp.expand(R[0][0]**3+R[1][1]**3-R[0][1]**3-R[1][0]**3),
    sp.expand(R[0][1]**3+R[1][2]**3-R[0][2]**3-R[1][1]**3),
    sp.expand(R[1][0]**3+R[2][1]**3-R[1][1]**3-R[2][0]**3),
    sp.expand(R[1][1]**3+R[2][2]**3-R[1][2]**3-R[2][1]**3),
]
for lhs,q in zip(rects,[Q00,Q01,Q10,Q11]):
    assert sp.expand(lhs + q) == 0

# Four vanishing adjacent mixed differences imply q_ij=C_i+T_j.
# Verify this by exact telescoping rather than a heavy Groebner computation.
q=[[sp.expand(R[i][jj]**3) for jj in range(3)] for i in range(3)]
M00=sp.expand(q[0][0]+q[1][1]-q[0][1]-q[1][0])
M01=sp.expand(q[0][1]+q[1][2]-q[0][2]-q[1][1])
M10=sp.expand(q[1][0]+q[2][1]-q[1][1]-q[2][0])
M11=sp.expand(q[1][1]+q[2][2]-q[1][2]-q[2][1])
assert sp.expand(M00-rects[0]) == 0
assert sp.expand(M01-rects[1]) == 0
assert sp.expand(M10-rects[2]) == 0
assert sp.expand(M11-rects[3]) == 0

res11=sp.expand(q[1][1]-q[1][0]-q[0][1]+q[0][0])
res12=sp.expand(q[1][2]-q[1][0]-q[0][2]+q[0][0])
res21=sp.expand(q[2][1]-q[2][0]-q[0][1]+q[0][0])
res22=sp.expand(q[2][2]-q[2][0]-q[0][2]+q[0][0])
assert sp.expand(res11-M00) == 0
assert sp.expand(res12-M00-M01) == 0
assert sp.expand(res21-M00-M10) == 0
assert sp.expand(res22-M00-M01-M10-M11) == 0

print('r27 exact root-grid certificate: PASS')
print('generic discriminant =', Delta_expected)
print('necessary congruence: each adjacent deficit d,e,f,g is 0 mod 3')
print('four Q equations are equivalent to a 3x3 Cartesian additive cube grid')
