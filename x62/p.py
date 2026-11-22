#!/usr/bin/env python3
import math,random,sys,time
import numpy as np
from scipy.optimize import milp,LinearConstraint,Bounds
from scipy.sparse import lil_matrix,csr_matrix
import b

def pb(q):
    for p in range(2,int(q**.5)+2):
        if q%p==0:
            z=q
            while z%p==0:z//=p
            if z==1:return p
    return q

def crt(rr,n):
    Q=math.prod(z[0] for z in rr);a=[0]*n
    for q,c,_,_ in rr:
        u=Q//q;w=u*pow(u,-1,q)
        for i,v in enumerate(c):a[i]=(a[i]+v*w)%Q
    return Q,a

def pack(S,n):
    G={}
    for z in S:
        if z[0]&1:G.setdefault(pb(z[0]),[]).append(z)
    R=max(map(len,G.values()));B=[[] for _ in range(R)];L=[0.]*R
    for _,rr in sorted(G.items(),key=lambda z:-sum(math.log2(x[0]) for x in z[1])):
        jj=sorted(range(R),key=lambda j:L[j])[:len(rr)]
        for j,z in zip(jj,sorted(rr,key=lambda x:-x[0])):B[j].append(z);L[j]+=math.log2(z[0])
    return [crt(z,n) for z in B]

def emit(path,L,sel=None):
    z=list(L)
    if sel is not None:z.append('idx='+','.join(map(str,sel)))
    open(path,'w').write('\n'.join(z)+'\n')

def model(path,k):
    P,_,_,_,_,S=b.build(path);n=len(P);O=pack(S,n);r=len(O);nv=n+r
    A=lil_matrix((r+1,nv),dtype=float);rhs=np.zeros(r+1);rhs[r]=k;hi=[]
    for j,(q,a) in enumerate(O):A[j,:n]=np.asarray(a,float);A[j,n+j]=-float(q);hi.append(sum(sorted(a,reverse=True)[:k])//q)
    A[r,:n]=1.;bd=Bounds(np.r_[np.zeros(n+r)],np.r_[np.ones(n),np.asarray(hi,float)]);ig=np.r_[np.zeros(n,dtype=int),np.ones(r,dtype=int)]
    return P,S,O,n,r,nv,LinearConstraint(csr_matrix(A),rhs,rhs),bd,ig

def rounded(x,k,rng,rep,mode):
    v=x.copy()
    if rep or mode:
        eps=min(.35,.015*(1+rep)*(1+mode));v+=np.array([rng.uniform(-eps,eps) for _ in range(len(v))])
    z=np.argpartition(v,-k)[-k:];y=np.zeros(len(v),dtype=np.int8);y[z]=1
    if rep:
        one=np.flatnonzero(y);zero=np.flatnonzero(1-y);h=min(1+rep//2,12,len(one),len(zero))
        for i in rng.sample(one.tolist(),h):y[i]=0
        for i in rng.sample(zero.tolist(),h):y[i]=1
    return y

def run(path,seed,seconds,out,k,mode):
    P,S,O,n,r,nv,cons,bd,ig=model(path,k);rng=random.Random(seed);L=['seed=%d'%seed,'k=%d'%k,'mode=%d'%mode,'rows=%d'%r];emit(out,L);st=time.time()
    z=milp(np.zeros(nv),integrality=ig,bounds=bd,constraints=cons,options={'time_limit':min(90.,seconds/8),'presolve':True,'disp':False})
    if z.x is None:L+=['NO_ANCHOR','status=%d'%z.status,'msg='+str(z.message)];emit(out,L);return 3
    x=z.x[:n];seen={};best=1e99;bestsel=None;it=0
    while time.time()-st<seconds-5:
        y0=rounded(x,k,rng,0,0);key0=np.packbits(y0).tobytes();rep=seen.get(key0,0);y=rounded(x,k,rng,rep,mode);key=np.packbits(y).tobytes();seen[key]=seen.get(key,0)+1
        sel=np.flatnonzero(y).tolist();bad=[(q,a) for q,a in O if sum(a[i] for i in sel)%q]
        if not bad:
            odd=[z0 for z0 in S if z0[0]&1]
            if any(sum(a[i] for i in sel)%q for q,a,t,m in odd):raise RuntimeError('verify')
            L+=['FOUND','verified=1','size=%d'%len(sel),'fac='+','.join(str(P[i]) for i in sel)];emit(out,L,sel);print('FOUND',len(sel));return 0
        c0=1-2*y.astype(float);eps=(.002+.004*mode)*min(8,seen[key]);c0+=np.array([rng.uniform(-eps,eps) for _ in range(n)])
        c=np.r_[c0,np.zeros(r)];left=seconds-(time.time()-st);lim=min(35.,max(4.,left/(2 if left>70 else 1)))
        z=milp(c,integrality=ig,bounds=bd,constraints=cons,options={'time_limit':lim,'presolve':True,'disp':False})
        if z.x is None:L+=['i%d=NONE,%d'%(it,z.status)];emit(out,L);it+=1;continue
        x=z.x[:n];dist=float(np.sum(np.where(y,1-x,x)));frac=int(np.sum((x>1e-7)&(x<1-1e-7)))
        if dist<best:best=dist;bestsel=sel
        L+=['i%d=s%d,d%.9f,f%d,b%d'%(it,z.status,dist,frac,len(bad)),'best=%.9f'%best];emit(out,L,bestsel);it+=1
        if it%12==0:
            q=np.r_[np.array([rng.uniform(-1,1) for _ in range(n)]),np.zeros(r)];left=seconds-(time.time()-st)
            z2=milp(q,integrality=ig,bounds=bd,constraints=cons,options={'time_limit':min(20.,max(2.,left/3)),'presolve':True,'disp':False})
            if z2.x is not None:x=z2.x[:n]
    L+=['OPEN','iterations=%d'%it,'best=%.9f'%best,'sec=%.3f'%(time.time()-st)];emit(out,L,bestsel);print('END',it,best);return 2
if __name__=='__main__':
    if len(sys.argv)!=7:raise SystemExit(1)
    raise SystemExit(run(sys.argv[1],int(sys.argv[2]),float(sys.argv[3]),sys.argv[4],int(sys.argv[5]),int(sys.argv[6])))
