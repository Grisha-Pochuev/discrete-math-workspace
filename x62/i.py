#!/usr/bin/env python3
import math,random,sys,time
import b
from ortools.sat.python import cp_model

def pb(q):
    for p in range(2,int(q**.5)+2):
        if q%p==0:
            z=q
            while z%p==0:z//=p
            if z==1:return p
    return q

def crt(rows,n):
    Q=math.prod(r[0] for r in rows); c=[0]*n; t=0
    for q,a,b0,_ in rows:
        u=Q//q; w=u*pow(u,-1,q)
        t=(t+b0*w)%Q
        for i,v in enumerate(a): c[i]=(c[i]+v*w)%Q
    return (Q,c,t,None)

def packodd(split,n):
    G={}
    for r in split:
        if r[0]&1:G.setdefault(pb(r[0]),[]).append(r)
    R=max(map(len,G.values())); bins=[[] for _ in range(R)]; load=[0.0]*R
    for p,rr in sorted(G.items(),key=lambda kv:-sum(math.log2(z[0]) for z in kv[1])):
        js=sorted(range(R),key=lambda j:load[j])[:len(rr)]
        for j,z in zip(js,sorted(rr,key=lambda z:-z[0])):
            bins[j].append(z);load[j]+=math.log2(z[0])
    out=[crt(z,n) for z in bins]
    if len(out)!=57 or max(z[0] for z in out)>100000:raise RuntimeError(('pack',len(out),max(z[0] for z in out)))
    return out

def er(m,x,row,k,tag):
    q,a,t,_=row;v=sorted(a);lo=sum(v[:k]);hi=sum(v[-k:]);zl=(lo-t+q-1)//q;zh=(hi-t)//q
    z=m.NewIntVar(zl,zh,tag);m.Add(sum(c*x[i] for i,c in enumerate(a) if c)-q*z==t)

def basis(coords,n):
    B=b.gf2_rref(b.gf2_rows(coords,n))
    if len(B)!=119:raise RuntimeError(('xor',len(B)))
    return [v for _,v in sorted(B.items())],B

def ax(m,x,R):
    for mask,rhs in R:
        z=[x[i] for i in range(len(x)) if (mask>>i)&1]
        m.AddBoolXOr(z if rhs else [z[0].Not()]+z[1:])

def phint(B,n,k,seed):
    piv=set(B);free=[i for i in range(n) if i not in piv];part=0
    for p,(_,rhs) in B.items():
        if rhs:part|=1<<p
    moves=[]
    for f in free:
        w=1<<f
        for p,(row,_) in B.items():
            if (row>>f)&1:w|=1<<p
        moves.append(w)
    rng=random.Random(seed^0x515621);best=part;bd=abs(part.bit_count()-k)
    for _ in range(4000):
        w=part
        for mv in moves:
            if rng.getrandbits(1):w^=mv
        d=abs(w.bit_count()-k)
        if d<bd:best,bd=w,d
        if d==0:break
    return [(best>>i)&1 for i in range(n)]

def ltasks(two,order,seed):
    T=[]
    for r,(q,a,t,meta) in enumerate(two):
        E=q.bit_length()-1
        for e in range(2,E+1):T.append((e,r))
    if len(T)!=123:raise RuntimeError(('lift',len(T)))
    rng=random.Random(seed^0x2ad1)
    if order==0:T.sort(key=lambda z:(z[0],sum(v!=0 for v in two[z[1]][1]),z[1]))
    elif order==1:T.sort(key=lambda z:(z[0],-sum(v!=0 for v in two[z[1]][1]),z[1]))
    else:
        U=[]
        for e in range(2,13):
            g=[z for z in T if z[0]==e];rng.shuffle(g);U+=g
        T=U
    return T

def verify(P,S,sol,k):
    if len(sol)!=k or not(k&1):raise RuntimeError(('k',len(sol)))
    for q,a,t,_ in S:
        if sum(a[i] for i in sol)%q!=t:raise RuntimeError(('row',q))
    N=1
    for i in sol:N*=P[i]
    for i in sol:
        p=P[i]
        if (N-1)%(p-1) or (N+1)%(p+1):raise RuntimeError(('direct',i,p))
    return N

def write(path,lines,prev=None):
    z=list(lines)
    if prev is not None:z.append('last='+','.join(str(i) for i,v in enumerate(prev) if v))
    open(path,'w').write('\n'.join(z)+'\n')

def run(path,seed,seconds,out,k,order,mode,batch):
    P,F,M,T,C,S=b.build(path);n=len(P);O=packodd(S,n);two=[r for r in S if not(r[0]&1)];X,B=basis(C,n);L=ltasks(two,order,seed)
    cuts=list(range(batch,123,batch))+[123];phases=[(0,False),(0,True)]+[(c,True) for c in cuts];lines=['seed=%d'%seed,'k=%d'%k,'odd=57','xor=119','lift=123','qmax=%d'%max(r[0] for r in O),'phases=%d'%len(phases)]
    prev=phint(B,n,k,seed);lines.append('hintk=%d'%sum(prev));write(out,lines,prev)
    st=time.time();re=-1
    for h,(cut,xon) in enumerate(phases):
        left=seconds-(time.time()-st)
        if left<8:break
        m=cp_model.CpModel();x=[m.NewBoolVar('x%d'%i) for i in range(n)];m.Add(sum(x)==k)
        for r,row in enumerate(O):er(m,x,row,k,'o%d'%r)
        if xon:ax(m,x,X)
        lev=[1]*len(two)
        for e,r in L[:cut]:lev[r]=max(lev[r],e)
        for r,e in enumerate(lev):
            if e<2:continue
            q=1<<e;row0=two[r];row=(q,[v%q for v in row0[1]],row0[2]%q,None);er(m,x,row,k,'t%d'%r)
        for i,v in enumerate(prev):m.AddHint(x[i],v)
        sv=cp_model.CpSolver();
        if h==0: budget=min(left-8.,max(240.,left*.32))
        elif h==1: budget=min(left-8.,max(180.,left*.25))
        else: budget=max(20.,left/(len(phases)-h))
        sv.parameters.max_time_in_seconds=budget;sv.parameters.num_search_workers=4;sv.parameters.random_seed=seed+1009*h;sv.parameters.randomize_search=True;sv.parameters.permute_variable_randomly=True;sv.parameters.permute_presolve_constraint_order=True;sv.parameters.stop_after_first_solution=True;sv.parameters.repair_hint=True;sv.parameters.hint_conflict_limit=1000000
        if mode==1:sv.parameters.search_branching=cp_model.PORTFOLIO_WITH_QUICK_RESTART_SEARCH
        elif mode==2:sv.parameters.linearization_level=0;sv.parameters.search_branching=cp_model.PORTFOLIO_WITH_QUICK_RESTART_SEARCH
        elif mode!=0:raise RuntimeError(('mode',mode))
        t0=time.time();s=sv.Solve(m);dt=time.time()-t0;name=sv.StatusName(s);lines.append('p%d=%s,x=%d,l=%d,sec=%.2f,br=%d,cf=%d'%(h,name,1 if xon else 0,cut,dt,sv.NumBranches(),sv.NumConflicts()))
        if s not in (cp_model.FEASIBLE,cp_model.OPTIMAL):write(out,lines,prev);break
        prev=[sv.Value(v) for v in x];re=h;write(out,lines,prev)
        if xon and cut==123:
            sol=[i for i,v in enumerate(prev) if v];N=verify(P,S,sol,k);lines+=['FOUND','fac='+','.join(str(P[i]) for i in sol),'N='+str(N)];write(out,lines,prev);print('FOUND',k);return 0
    lines+=['OPEN','reached=%d'%re,'sec=%.2f'%(time.time()-st)];write(out,lines,prev if re>=0 else None);print('END',re);return 2
if __name__=='__main__':
    if len(sys.argv)!=9:raise SystemExit(1)
    raise SystemExit(run(sys.argv[1],int(sys.argv[2]),float(sys.argv[3]),sys.argv[4],int(sys.argv[5]),int(sys.argv[6]),int(sys.argv[7]),int(sys.argv[8])))
