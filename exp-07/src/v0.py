#!/usr/bin/env python3
import argparse, csv, json, math
from fractions import Fraction
from pathlib import Path

TYPES=((0,0,1),(0,1,0),(0,1,1),(1,0,0),(1,0,1),(1,1,0))

def data(a,b):
    u=Fraction(a,b)
    P=1-u+3*u*u
    Q=1+u+3*u*u
    C=1-2*u-3*u*u*u
    D=1+2*u+3*u*u*u
    assert P>0 and Q>0 and C>0 and D>0
    assert P**3+Q**3==C**3+D**3
    return (P,Q,C,D)

def ratio(t,x):
    P,Q,C,D=x
    return P/Q if t==0 else C/D

def fdelta(t,x):
    P,Q,C,D=x
    return (D**3-C**3)/Q**3 if t==0 else (Q**3-P**3)/D**3

def alt(t,x):
    P,Q,C,D=x
    return (C/Q,D/Q) if t==0 else (P/D,Q/D)

def lcm(a,b): return a//math.gcd(a,b)*b

def clear(vals):
    L=1
    for q in vals:L=lcm(L,q.denominator)
    ints=[q.numerator*(L//q.denominator) for q in vals]
    g=0
    for z in ints:g=math.gcd(g,abs(z))
    return [z//g for z in ints]

def verify_record(type_id,row):
    ta,tb,tc=TYPES[type_id]
    ua,ub,va,vb,wa,wb=map(int,[row['ua'],row['ub'],row['va'],row['vb'],row['wa'],row['wb']])
    U,V,W=data(ua,ub),data(va,vb),data(wa,wb)
    ru,rv,rw=ratio(ta,U),ratio(tb,V),ratio(tc,W)
    if rw!=ru*rv:return None
    mags=[rv**3*fdelta(ta,U), fdelta(tb,V), fdelta(tc,W)]
    order=sorted(range(3),key=lambda k:mags[k])
    if mags[order[2]]!=mags[order[0]]+mags[order[1]]:return None
    s=[-1,-1,-1];s[order[2]]=1
    top=[rw,rv,Fraction(1)]
    ab=tuple(rv*x for x in alt(ta,U)); bc=alt(tb,V); ac=alt(tc,W)
    def orient(pair,sign):
        lo,hi=sorted(pair)
        return (hi,lo) if sign>0 else (lo,hi)
    f,i=orient(ab,s[0]); d,g=orient(bc,s[1]); e,h=orient(ac,s[2])
    vals=[top[0],top[1],top[2],d,e,f,g,h,i]
    ints=clear(vals)
    if min(ints)<=0 or len(set(ints))!=9:return None
    cubes=[z**3 for z in ints]
    sums=[sum(cubes[0:3]),sum(cubes[3:6]),sum(cubes[6:9]),cubes[0]+cubes[3]+cubes[6],cubes[1]+cubes[4]+cubes[7],cubes[2]+cubes[5]+cubes[8]]
    if len(set(sums))!=1:return None
    return {'type':type_id,'params':[[ua,ub],[va,vb],[wa,wb]],'bases':ints,'S':sums[0]}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--type',type=int,required=True);ap.add_argument('--input',nargs='+',required=True);ap.add_argument('--output',required=True)
    args=ap.parse_args(); checked=exact_ratio=exact_cancel=0; sols=[]
    for p in args.input:
        path=Path(p)
        if not path.exists(): continue
        with path.open() as f:
            for row in csv.DictReader(f,delimiter='\t'):
                checked+=1
                ta,tb,tc=TYPES[args.type]
                U=data(int(row['ua']),int(row['ub']));V=data(int(row['va']),int(row['vb']));W=data(int(row['wa']),int(row['wb']))
                if ratio(tc,W)==ratio(ta,U)*ratio(tb,V): exact_ratio+=1
                mags=[ratio(tb,V)**3*fdelta(ta,U),fdelta(tb,V),fdelta(tc,W)]
                so=sorted(mags)
                if so[2]==so[0]+so[1]:exact_cancel+=1
                sol=verify_record(args.type,row)
                if sol:sols.append(sol)
    result={'type':args.type,'near_records_checked':checked,'exact_ratio_records':exact_ratio,'exact_cancellations':exact_cancel,'solutions':sols}
    Path(args.output).write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
