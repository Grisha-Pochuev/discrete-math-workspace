#!/usr/bin/env python3
import math,random,sys,time
import numpy as np
from scipy.optimize import milp,LinearConstraint,Bounds
from scipy.sparse import lil_matrix,csr_matrix
from ortools.sat.python import cp_model
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
    O=[crt(z,n) for z in B]
    if len(O)!=57 or max(q for q,_ in O)>100000:raise RuntimeError('pack')
    return O

def anchor(O,n,k,seed):
    rng=random.Random(seed^0x5a6217);pm=list(range(n));rng.shuffle(pm);r=len(O);nv=n+r
    A=lil_matrix((r+1,nv),dtype=float);rhs=np.zeros(r+1);zh=[]
    for j,(q,a) in enumerate(O):
        c=[a[i] for i in pm];A[j,:n]=np.asarray(c,float);A[j,n+j]=-float(q);zh.append(sum(sorted(c,reverse=True)[:k])//q)
    A[r,:n]=1.;rhs[r]=k
    lo=np.r_[np.zeros(n),np.zeros(r)];hi=np.r_[np.ones(n),np.asarray(zh,float)]
    it=np.r_[np.zeros(n,dtype=int),np.ones(r,dtype=int)]
    z=milp(np.zeros(nv),integrality=it,bounds=Bounds(lo,hi),constraints=LinearConstraint(csr_matrix(A),rhs,rhs),options={'time_limit':18.,'presolve':True,'disp':False})
    if z.x is None:raise RuntimeError(('anchor',z.status,z.message))
    x=[0.]*n
    for j,i in enumerate(pm):x[i]=float(z.x[j])
    fr=[i for i,v in enumerate(x) if 1e-7<v<1-1e-7];iv=[i for i,v in enumerate(x) if v<=1e-7 or v>=1-1e-7]
    return x,fr,iv

def order(O,o,seed):
    O=list(O)
    if o==0:O.sort(key=lambda z:(z[0],))
    elif o==1:O.sort(key=lambda z:(-z[0],))
    elif o==2:random.Random(seed^0x621bad).shuffle(O)
    else:raise RuntimeError(o)
    return O

def ar(m,x,q,a,k,tag):
    v=sorted(a);lo=sum(v[:k]);hi=sum(v[-k:]);z=m.NewIntVar(max(0,(lo+q-1)//q),hi//q,tag);m.Add(sum(c*x[i] for i,c in enumerate(a) if c)==q*z)

def wr(path,L,sol=None):
    z=list(L)
    if sol is not None:z.append('idx='+','.join(map(str,sol)))
    open(path,'w').write('\n'.join(z)+'\n')

def run(path,seed,seconds,out,k,nfix,o,mode,batch):
    P,_,_,_,_,S=b.build(path);n=len(P);O=pack(S,n);a,fr,iv=anchor(O,n,k,seed);rng=random.Random(seed^0xf162);rng.shuffle(iv)
    if nfix>len(iv):raise RuntimeError(('fix',nfix,len(iv)))
    F={i:int(a[i]>=.5) for i in iv[:nfix]};top=set(sorted(range(n),key=lambda i:a[i],reverse=True)[:k]);h=[int(i in top) for i in range(n)]
    for i,v in F.items():h[i]=v
    d=k-sum(h);free=[i for i in range(n) if i not in F]
    if d>0:
        for i in sorted((i for i in free if not h[i]),key=lambda i:-a[i])[:d]:h[i]=1
    elif d<0:
        for i in sorted((i for i in free if h[i]),key=lambda i:a[i])[:-d]:h[i]=0
    if sum(h)!=k:raise RuntimeError(('hint',sum(h),k))
    O=order(O,o,seed);cuts=list(range(batch,len(O),batch))+[len(O)];L=['seed=%d'%seed,'k=%d'%k,'fix=%d'%nfix,'fone=%d'%sum(F.values()),'frac=%d'%len(fr),'rows=%d'%len(O),'qmax=%d'%max(q for q,_ in O),'order=%d'%o,'mode=%d'%mode,'batch=%d'%batch];wr(out,L)
    st=time.time();prev=h;re=0
    for ph,cut in enumerate(cuts):
        left=seconds-(time.time()-st)
        if left<8:L.append('p%d=NO_TIME'%ph);break
        m=cp_model.CpModel();x=[m.NewBoolVar('x%d'%i) for i in range(n)];m.Add(sum(x)==k)
        for i,v in F.items():m.Add(x[i]==v)
        for ri,(q,c) in enumerate(O[:cut]):ar(m,x,q,c,k,'z%d'%ri)
        for i,v in enumerate(prev):m.AddHint(x[i],v)
        sv=cp_model.CpSolver();sv.parameters.max_time_in_seconds=max(12.,left/(len(cuts)-ph));sv.parameters.num_search_workers=4;sv.parameters.random_seed=seed+1009*ph;sv.parameters.randomize_search=True;sv.parameters.permute_variable_randomly=True;sv.parameters.permute_presolve_constraint_order=True;sv.parameters.stop_after_first_solution=True;sv.parameters.repair_hint=True;sv.parameters.hint_conflict_limit=1000000
        if mode==1:sv.parameters.search_branching=cp_model.PORTFOLIO_WITH_QUICK_RESTART_SEARCH
        elif mode==2:sv.parameters.linearization_level=0;sv.parameters.search_branching=cp_model.PORTFOLIO_WITH_QUICK_RESTART_SEARCH
        elif mode!=0:raise RuntimeError(mode)
        t=time.time();s=sv.Solve(m);dt=time.time()-t;name=sv.StatusName(s);L.append('p%d=%s,r=%d,sec=%.3f,br=%d,cf=%d'%(ph,name,cut,dt,sv.NumBranches(),sv.NumConflicts()));wr(out,L)
        if s not in (cp_model.FEASIBLE,cp_model.OPTIMAL):break
        prev=[sv.Value(v) for v in x];re=cut
        if cut==len(O):
            sol=[i for i,v in enumerate(prev) if v];odd=[z for z in S if z[0]&1]
            if len(sol)!=k or any(sum(c[i] for i in sol)%q for q,c,_,_ in odd):raise RuntimeError('verify')
            two=[(q,sum(c[i] for i in sol)%q,t) for q,c,t,_ in S if not(q&1)];L+=['FOUND','verified=1','two=%d/%d'%(sum(v==t for q,v,t in two),len(two)),'fac='+','.join(str(P[i]) for i in sol)];wr(out,L,sol);print('FOUND',k,nfix);return 0
    L+=['OPEN','reached=%d'%re,'sec=%.3f'%(time.time()-st)];wr(out,L);print('END',k,nfix,re);return 2
if __name__=='__main__':
    if len(sys.argv)!=10:raise SystemExit(1)
    raise SystemExit(run(sys.argv[1],int(sys.argv[2]),float(sys.argv[3]),sys.argv[4],int(sys.argv[5]),int(sys.argv[6]),int(sys.argv[7]),int(sys.argv[8]),int(sys.argv[9])))
