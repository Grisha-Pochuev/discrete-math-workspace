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
    Q=math.prod(r[0] for r in rows);c=[0]*n;t=0
    for q,a,b0,_ in rows:
        u=Q//q;w=u*pow(u,-1,q);t=(t+b0*w)%Q
        for i,v in enumerate(a):c[i]=(c[i]+v*w)%Q
    return Q,c,t,None

def pack(split,n):
    G={}
    for r in split:
        if r[0]&1:G.setdefault(pb(r[0]),[]).append(r)
    R=max(map(len,G.values()));bins=[[] for _ in range(R)];load=[0.0]*R
    for p,rr in sorted(G.items(),key=lambda kv:-sum(math.log2(z[0]) for z in kv[1])):
        js=sorted(range(R),key=lambda j:load[j])[:len(rr)]
        for j,z in zip(js,sorted(rr,key=lambda z:-z[0])):
            bins[j].append(z);load[j]+=math.log2(z[0])
    out=[crt(z,n) for z in bins]
    if len(out)!=57 or any(z[2] for z in out):raise RuntimeError('pack')
    return out

def run(path,seed,seconds,out,mode):
    P,_,_,_,C,S=b.build(path);n=len(P);O=pack(S,n)
    m=cp_model.CpModel();x=[m.NewBoolVar('x%d'%i) for i in range(n)]
    k=m.NewIntVar(1,n,'k');h=m.NewIntVar(0,n//2,'h');m.Add(k==sum(x));m.Add(k==2*h+1)
    for r,(q,a,t,_) in enumerate(O):
        z=m.NewIntVar(0,sum(a)//q,'z%d'%r)
        m.Add(sum(v*x[i] for i,v in enumerate(a) if v)-q*z==0)
    rng=random.Random(seed)
    hint=[rng.getrandbits(1) for _ in range(n)]
    if sum(hint)%2==0:hint[rng.randrange(n)]^=1
    for i,v in enumerate(hint):m.AddHint(x[i],v)
    m.AddHint(k,sum(hint))
    sv=cp_model.CpSolver();sv.parameters.max_time_in_seconds=float(seconds);sv.parameters.num_search_workers=4
    sv.parameters.random_seed=seed;sv.parameters.randomize_search=True;sv.parameters.permute_variable_randomly=True;sv.parameters.permute_presolve_constraint_order=True;sv.parameters.stop_after_first_solution=True;sv.parameters.repair_hint=True;sv.parameters.hint_conflict_limit=1000000
    if mode==1:sv.parameters.search_branching=cp_model.PORTFOLIO_WITH_QUICK_RESTART_SEARCH
    elif mode==2:sv.parameters.linearization_level=0;sv.parameters.search_branching=cp_model.PORTFOLIO_WITH_QUICK_RESTART_SEARCH
    elif mode==3:sv.parameters.use_ls_only=True;sv.parameters.use_feasibility_jump=True
    elif mode!=0:raise RuntimeError(mode)
    t0=time.time();st=sv.Solve(m);dt=time.time()-t0;name=sv.StatusName(st)
    lines=['seed=%d'%seed,'mode=%d'%mode,'status='+name,'sec=%.3f'%dt,'br=%d'%sv.NumBranches(),'cf=%d'%sv.NumConflicts()]
    if st in (cp_model.FEASIBLE,cp_model.OPTIMAL):
        sol=[i for i in range(n) if sv.Value(x[i])]
        bad=[(q,meta) for q,a,t,meta in S if q&1 and sum(a[i] for i in sol)%q]
        two=[(q,sum(a[i] for i in sol)%q,t) for q,a,t,_ in S if not(q&1)]
        if bad or not(len(sol)&1):raise RuntimeError(('verify',len(sol),len(bad)))
        lines+=['FOUND','k=%d'%len(sol),'two=%d/%d'%(sum(v==t for q,v,t in two),len(two)),'idx='+','.join(map(str,sol))]
        rc=0
    else:rc=2
    open(out,'w').write('\n'.join(lines)+'\n');print('\n'.join(lines));return rc

if __name__=='__main__':
    if len(sys.argv)!=6:raise SystemExit(1)
    raise SystemExit(run(sys.argv[1],int(sys.argv[2]),float(sys.argv[3]),sys.argv[4],int(sys.argv[5])))
