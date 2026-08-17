#!/usr/bin/env python3
import argparse, json, math, random, time
from fractions import Fraction as F

TYPES=((0,0,1),(0,1,0),(0,1,1),(1,0,0),(1,0,1),(1,1,0))
BANDS=((3,100),(101,1000),(1001,10000),(10001,100000),(100001,1000000))

def cube(x): return x*x*x

def ev(a,b):
    a,b=int(a),int(b)
    p=b*b-a*b+3*a*a; q=b*b+a*b+3*a*a
    c=b**3-2*a*b*b-3*a**3; d=b**3+2*a*b*b+3*a**3
    return {
        'r':(F(p,q),F(c,d)),
        'f':(F(d**3-c**3,q**3*b**3), F(b**3*(q**3-p**3),d**3)),
        'alt':((F(c,q*b),F(d,q*b)),(F(p*b,d),F(q*b,d)))
    }

def sample(g,lo,hi):
    while True:
        b=g.randint(lo,hi)
        if b<3: continue
        a=g.randint(1,(b-1)//2)
        if math.gcd(a,b)==1: return a,b

def reconstruct(tt,ee,big):
    a=ee[2]['r'][tt[2]]; b=ee[1]['r'][tt[1]]
    z=[a,b,F(1),None,None,None,None,None,None]
    pairs=[list(ee[1]['alt'][tt[1]]),list(ee[2]['alt'][tt[2]]),list(ee[0]['alt'][tt[0]])]
    pairs[2]=[x*b for x in pairs[2]]
    for k,(lo,hi) in enumerate(pairs):
        first,second=(hi,lo) if k==big else (lo,hi)
        if k==0: z[3],z[6]=first,second
        elif k==1: z[4],z[7]=first,second
        else: z[5],z[8]=first,second
    if any(x<=0 for x in z) or len(set(z))!=9: return None
    L=1
    for x in z: L=math.lcm(L,x.denominator)
    ints=[x.numerator*(L//x.denominator) for x in z]
    G=0
    for x in ints: G=math.gcd(G,abs(x))
    if G>1: ints=[x//G for x in ints]
    c=[x**3 for x in ints]
    sums=[sum(c[0:3]),sum(c[3:6]),sum(c[6:9]),c[0]+c[3]+c[6],c[1]+c[4]+c[7],c[2]+c[5]+c[8]]
    if len(set(sums))!=1: return None
    return {'bases':ints,'S':str(sums[0])}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--worker',type=int,default=0); ap.add_argument('--workers',type=int,default=1); ap.add_argument('--seconds',type=int,default=30); ap.add_argument('--seed',type=int,default=20260817); ap.add_argument('--out',default='-'); args=ap.parse_args()
    g=random.Random(args.seed ^ (0x9e3779b97f4a7c15*(args.worker+1)))
    attempts=compatible=cancellations=0; attb=[0]*6; compb=[0]*6; found=[]; start=time.monotonic()
    while True:
        if attempts%256==0 and time.monotonic()-start>=args.seconds: break
        bi=attempts%6; tt=TYPES[bi]; dep=0 if tt[0]==0 else (1 if tt[1]==0 else 2)
        lo,hi=BANDS[(args.worker+attempts//6)%len(BANDS)]
        ee=[None,None,None]
        for j in range(3):
            if j!=dep: ee[j]=ev(*sample(g,lo,hi))
        if dep==0: target=ee[2]['r'][tt[2]]/ee[1]['r'][tt[1]]
        elif dep==1: target=ee[2]['r'][tt[2]]/ee[0]['r'][tt[0]]
        else: target=ee[0]['r'][tt[0]]*ee[1]['r'][tt[1]]
        attempts+=1; attb[bi]+=1
        if not (0<target<1 and 9*target>5): continue
        dn=target.denominator-target.numerator; sp=target.denominator+target.numerator
        disc=sp*sp-12*dn*dn
        if disc<0: continue
        rt=math.isqrt(disc)
        if rt*rt!=disc: continue
        for sgn in (-1,1):
            xn=sp+sgn*rt; xd=6*dn
            if xn<=0 or 2*xn>=xd: continue
            x=F(xn,xd); ee[dep]=ev(x.numerator,x.denominator)
            if dep==0: check=ee[2]['r'][tt[2]]/ee[1]['r'][tt[1]]
            elif dep==1: check=ee[2]['r'][tt[2]]/ee[0]['r'][tt[0]]
            else: check=ee[0]['r'][tt[0]]*ee[1]['r'][tt[1]]
            if ee[dep]['r'][0]!=check: continue
            compatible+=1; compb[bi]+=1
            ds=[ee[1]['r'][tt[1]]**3*ee[0]['f'][tt[0]],ee[1]['f'][tt[1]],ee[2]['f'][tt[2]]]
            order=sorted(range(3),key=lambda k:ds[k])
            if ds[order[0]]+ds[order[1]]!=ds[order[2]]: continue
            cancellations+=1
            rec=reconstruct(tt,ee,order[2])
            if rec: rec['case']=bi; found.append(rec)
            break
    data={'worker':args.worker,'workers':args.workers,'attempts':attempts,'compatible':compatible,'cancellations':cancellations,'elapsed':time.monotonic()-start,'attempts_by_case':attb,'compatible_by_case':compb,'found':found}
    text=json.dumps(data,separators=(',',':'))
    if args.out=='-': print(text)
    else: open(args.out,'w').write(text+'\n')

if __name__=='__main__': main()
