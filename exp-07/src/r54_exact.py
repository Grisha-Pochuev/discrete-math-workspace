#!/usr/bin/env python3
"""Exact transverse multiplicity audit for TRI lines emitted by r54_bounded.cpp."""
import argparse, math, re
from functools import lru_cache
import sympy as sp

TRI_RE=re.compile(r"^TRI D=(\d+) lower=(\d+),(\d+),(\d+) upper=(\d+),(\d+),(\d+) g=(\d+)$")

@lru_cache(None)
def reps(K:int):
    out=[]
    for d in sp.divisors(K):
        M=K//d
        disc=12*M-3*d*d
        if disc<=0:
            continue
        s=math.isqrt(disc)
        if s*s!=disc or s<=3*d or (s-3*d)%6:
            continue
        x=(s-3*d)//6
        y=x+d
        if x>0 and y**3-x**3==K:
            out.append((x,y))
    return tuple(sorted(set(out)))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('triples')
    a=ap.parse_args()
    n=0; all3=[]
    for raw in open(a.triples):
        m=TRI_RE.match(raw.strip())
        if not m: continue
        D,x0,x1,x2,y0,y1,y2,g=map(int,m.groups()); n+=1
        K01=x1**3-x0**3; K12=x2**3-x1**3; K02=x2**3-x0**3
        mult=(len(reps(K01)),len(reps(K12)),len(reps(K02)))
        if min(mult)>=3:
            all3.append((D,(x0,x1,x2),(y0,y1,y2),g,mult))
            print(f'ALL3_EXACT D={D} lower={x0},{x1},{x2} upper={y0},{y1},{y2} g={g} mult={mult[0]},{mult[1]},{mult[2]}')
    prim=sum(g==1 for *_,g,_ in all3)
    print(f'STAT triples={n} all3_exact={len(all3)} primitive_all3={prim} cached_K={reps.cache_info().currsize}')

if __name__=='__main__': main()
