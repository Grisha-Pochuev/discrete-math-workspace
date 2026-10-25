#!/usr/bin/env python3
import math,random,sys,time
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

def emit(path,L):
    open(path,'w').write('\n'.join(L)+'\n')

def run(path,seed,seconds,out,form,pair,k,fix):
    from pyscipopt import Model,quicksum
    P,_,_,_,_,S=b.build(path);n=len(P);rng=random.Random(seed)
    if form==0:O=pack(S,n)
    elif form==1:O=[(q,a) for q,a,t,_ in S if q&1]
    else:raise RuntimeError(form)
    M=Model('m');x=[M.addVar(vtype='B',name='x%d'%i) for i in range(n)]
    if k>0:M.addCons(quicksum(x)==k)
    else:
        h=M.addVar(vtype='I',lb=1,ub=(n-1)//2,name='h');M.addCons(quicksum(x)-2*h==1)
    for ri,(q,a) in enumerate(O):
        z=M.addVar(vtype='I',lb=0,ub=sum(a)//q,name='z%d'%ri)
        M.addCons(quicksum(v*x[i] for i,v in enumerate(a) if v)-q*z==0)
    ids=list(range(n));rng.shuffle(ids)
    if pair:
        for j in range(0,n-1,2):
            if pair==1:M.addCons(x[ids[j]]+x[ids[j+1]]<=1)
            elif pair==2:M.addCons(x[ids[j]]+x[ids[j+1]]>=1)
            else:raise RuntimeError(pair)
    if fix:
        for i in ids[:fix]:M.addCons(x[i]==rng.getrandbits(1))
    for name,val in [('limits/time',float(seconds)),('limits/solutions',1),('randomization/randomseedshift',seed%2147483647),('randomization/permutevars',True),('randomization/permutationseed',seed%2147483647),('parallel/maxnthreads',4),('display/verblevel',4)]:
        try:M.setParam(name,val)
        except Exception:pass
    try:
        from pyscipopt import SCIP_PARAMSETTING
        M.setHeuristics(SCIP_PARAMSETTING.AGGRESSIVE)
    except Exception:pass
    L=['seed=%d'%seed,'form=%d'%form,'pair=%d'%pair,'k=%d'%k,'fix=%d'%fix,'rows=%d'%len(O)];emit(out,L)
    t=time.time();M.optimize();dt=time.time()-t;L+=['status='+str(M.getStatus()),'sec=%.3f'%dt,'nodes=%d'%M.getNNodes(),'sols=%d'%M.getNSols()]
    if M.getNSols():
        soln=M.getBestSol();sel=[i for i in range(n) if M.getSolVal(soln,x[i])>.5]
        odd=[z for z in S if z[0]&1];bad=[(q,meta) for q,a,t,meta in odd if sum(a[i] for i in sel)%q]
        if bad:raise RuntimeError(('verify',len(bad)))
        two=[(q,sum(a[i] for i in sel)%q,t) for q,a,t,_ in S if not(q&1)]
        L+=['FOUND','verified=1','size=%d'%len(sel),'two=%d/%d'%(sum(v==t for q,v,t in two),len(two)),'idx='+','.join(map(str,sel)),'fac='+','.join(str(P[i]) for i in sel)];emit(out,L);print('FOUND',len(sel));return 0
    L+=['OPEN'];emit(out,L);print('END',M.getStatus(),M.getNNodes());return 2
if __name__=='__main__':
    if len(sys.argv)!=10:raise SystemExit(1)
    raise SystemExit(run(sys.argv[1],int(sys.argv[2]),float(sys.argv[3]),sys.argv[4],int(sys.argv[5]),int(sys.argv[6]),int(sys.argv[7]),int(sys.argv[8])))
