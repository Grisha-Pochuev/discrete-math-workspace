#!/usr/bin/env python3
"""Exact rational orbit probe for a two-layer diagonal-cubic strip.

Input is TRI output from r54_bounded.cpp.  All arithmetic is Fraction-exact.
No bound is imposed on the integer roots obtained after clearing denominators.
"""
from __future__ import annotations
import argparse, math, re
from fractions import Fraction
from typing import Tuple

TRI_RE=re.compile(r"^TRI D=(\d+) lower=(\d+),(\d+),(\d+) upper=(\d+),(\d+),(\d+) g=(\d+)$")
Point=Tuple[Fraction,Fraction,Fraction]

def norm_proj(P:Point)->tuple[int,int,int]:
    den=1
    for x in P: den=math.lcm(den,x.denominator)
    z=[x.numerator*(den//x.denominator) for x in P]
    g=0
    for x in z: g=math.gcd(g,abs(x))
    if g: z=[x//g for x in z]
    for x in z:
        if x:
            if x<0: z=[-u for u in z]
            break
    return tuple(z)

def as_point(P)->Point:
    return tuple(Fraction(x) for x in norm_proj(tuple(Fraction(x) for x in P)))

def make_curve(lam:Fraction):
    lam=Fraction(lam); ca=lam-1; cb=-lam; cc=Fraction(1)
    O=as_point((1,1,1))
    def F(P:Point):
        a,b,c=P; return ca*a**3+cb*b**3+cc*c**3
    def third(P:Point,Q:Point)->Point:
        P=as_point(P); Q=as_point(Q)
        if norm_proj(P)!=norm_proj(Q):
            a,b,c=P; u,v,w=Q
            c1=3*(ca*a*a*u+cb*b*b*v+cc*c*c*w)
            c2=3*(ca*a*u*u+cb*b*v*v+cc*c*w*w)
            if c2==0:
                if c1==0: raise ArithmeticError('line component on smooth cubic')
                R=Q
            else:
                t=-c1/c2
                R=(a+t*u,b+t*v,c+t*w)
        else:
            a,b,c=P
            V=(cb*b*b,-ca*a*a,Fraction(0))
            if V==(0,0,0) or norm_proj(V)==norm_proj(P):
                V=(cc*c*c,Fraction(0),-ca*a*a)
            u,v,w=V
            c2=3*(ca*a*u*u+cb*b*v*v+cc*c*w*w)
            c3=ca*u**3+cb*v**3+cc*w**3
            if c3==0: R=V
            else:
                t=-c2/c3
                R=(a+t*u,b+t*v,c+t*w)
        R=as_point(R)
        if F(R)!=0: raise ArithmeticError('third point failed curve equation')
        return R
    H=third(O,O)
    def neg(P:Point)->Point: return third(P,H)
    def add(P:Point,Q:Point)->Point: return third(third(P,Q),O)
    def mul(P:Point,n:int)->Point:
        if n<0: return mul(neg(P),-n)
        R=O; B=P
        while n:
            if n&1: R=add(R,B)
            n//=2
            if n: B=add(B,B)
        return R
    return F,O,add,neg,mul

def icbrt(n:int)->int:
    if n<0:return -icbrt(-n)
    if n<2:return n
    lo=0; hi=1
    while hi**3<=n: hi*=2
    while lo+1<hi:
        m=(lo+hi)//2
        if m**3<=n: lo=m
        else: hi=m
    return lo

def cube_int(n:int)->bool:
    r=icbrt(n); return r**3==n

def same_cube_class(x:int,y:int)->bool:
    if not x or not y:return False
    q=Fraction(x,y)
    return cube_int(q.numerator) and cube_int(q.denominator)

def delta(P:Point)->int:
    a,b,_=norm_proj(P); return b**3-a**3

def positive(P:Point)->bool:
    return min(norm_proj(P))>0

def lam_of(P)->Fraction:
    a,b,c=map(int,P); return Fraction(c**3-a**3,b**3-a**3)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('triples')
    ap.add_argument('--n-min',type=int,default=-3)
    ap.add_argument('--n-max',type=int,default=4)
    ap.add_argument('--limit',type=int,default=0)
    a=ap.parse_args()
    rows=[]
    for raw in open(a.triples):
        m=TRI_RE.match(raw.strip())
        if not m: continue
        D,x0,x1,x2,y0,y1,y2,g=map(int,m.groups())
        rows.append((D,(x0,x1,x2),(y0,y1,y2),g))
        if a.limit and len(rows)>=a.limit: break
    tested=class_hits=positive_hits=0
    for D,low,up,g in rows:
        lam=lam_of(low)
        if lam_of(up)!=lam: raise ArithmeticError('lambda replay')
        F,O,add,neg,mul=make_curve(lam)
        P0=as_point(low); P1=as_point(up)
        if F(P0)!=0 or F(P1)!=0: raise ArithmeticError('input off curve')
        T=add(P1,neg(P0)); d0=delta(P0)
        P=add(P0,mul(T,a.n_min))
        for n in range(a.n_min,a.n_max+1):
            if n!=a.n_min: P=add(P,T)
            if n in (0,1): continue
            tested+=1; d=delta(P)
            if same_cube_class(d,d0):
                class_hits+=1; pos=positive(P); positive_hits+=int(pos)
                z=norm_proj(P); ratio=Fraction(d,d0)
                print(f'HIT n={n} D={D} low={low[0]},{low[1]},{low[2]} upper={up[0]},{up[1]},{up[2]} point={z[0]},{z[1]},{z[2]} ratio={ratio.numerator}/{ratio.denominator} positive={int(pos)}')
    print(f'STAT triples={len(rows)} n_min={a.n_min} n_max={a.n_max} tested_points={tested} cube_class_hits={class_hits} positive_hits={positive_hits}')

if __name__=='__main__': main()
