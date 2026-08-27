#!/usr/bin/env python3
import math, random, sys, time
import b


def build_local(data_path):
    P,F,maxe,targets,coords,split=b.build(data_path)
    acts={}
    rows=[]
    for r,E in sorted(maxe.items()):
        for e in range(1,E+1):
            idx=[i for i,f in enumerate(F) if f.get(r,0)>=e]
            if not idx: raise RuntimeError(('empty',r,e))
            h=r**e
            vals={P[i]%h for i in idx}
            if len(vals)!=1: raise RuntimeError(('target',r,e,len(vals)))
            t=next(iter(vals)); acts[(r,e)]=idx
            if r==2:
                if e==1: continue
                if e==2:
                    aa=[0 if p%4==1 else 1 for p in P]
                    bb=0 if t%4==1 else 1
                    rows.append((r,e,2,aa,bb))
                else:
                    tab=b.two_table(e)
                    aa=[b.two_coords(p,e,tab)[1] for p in P]
                    bb=b.two_coords(t,e,tab)[1]
                    m=1<<(e-2)
                    if m>1: rows.append((r,e,m,aa,bb))
            else:
                m=(r-1)*(r**(e-1)); g=b.primitive_root_prime_power(r,e); tab=b.dlog_table(h,g,m)
                aa=[tab[p%h] for p in P]; bb=tab[t]
                rows.append((r,e,m,aa,bb))
    if len(acts)!=160 or len(rows)!=159: raise RuntimeError(('counts',len(acts),len(rows)))
    return P,F,maxe,targets,acts,rows


def model_ok(sel,acts,rows):
    S=set(sel)
    for r,e,m,aa,bb in rows:
        if any(i in S for i in acts[(r,e)]):
            if sum(aa[i] for i in sel)%m!=bb:return False
    return True


def direct_ok(P,sel):
    N=1
    for i in sel:N*=P[i]
    return all((N-1)%(P[i]-1)==0 and (N+1)%(P[i]+1)==0 for i in sel)


def check(path):
    P,F,maxe,targets,acts,rows=build_local(path)
    rng=random.Random(62066)
    for _ in range(100):
        k=rng.choice([3,5,7,9,11,13,15])
        sel=rng.sample(range(len(P)),k)
        a=model_ok(sel,acts,rows);d=direct_ok(P,sel)
        if a!=d: raise RuntimeError(('equiv',k,sel,a,d))
    print('CHECK2 n=%d acts=%d rows=%d maxm=%d'%(len(P),len(acts),len(rows),max(z[2] for z in rows)))


def solve(path,k,seed,seconds,out,mode=0):
    from ortools.sat.python import cp_model
    P,F,maxe,targets,acts,rows=build_local(path)
    n=len(P); model=cp_model.CpModel(); x=[model.NewBoolVar('x%d'%i) for i in range(n)]
    model.Add(sum(x)==k)
    y={}
    for key,idx in acts.items():
        v=model.NewBoolVar('y%d_%d'%key); y[key]=v
        model.AddMaxEquality(v,[x[i] for i in idx])
    for r in sorted(maxe):
        for e in range(1,maxe[r]): model.Add(y[(r,e+1)]<=y[(r,e)])
    for ri,(r,e,m,aa,bb) in enumerate(rows):
        nz=[(a,x[i]) for i,a in enumerate(aa) if a]
        total=sum(sorted((a for a,_ in nz),reverse=True)[:k])
        zmax=max(0,(total-bb)//m)
        z=model.NewIntVar(0,zmax,'z%d'%ri)
        model.Add(sum(a*v for a,v in nz)-m*z==bb).OnlyEnforceIf(y[(r,e)])
    rng=random.Random(seed); hs=set(rng.sample(range(n),k))
    for i,v in enumerate(x):model.AddHint(v,1 if i in hs else 0)
    solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=float(seconds);solver.parameters.num_search_workers=4
    solver.parameters.random_seed=seed;solver.parameters.randomize_search=True;solver.parameters.permute_variable_randomly=True;solver.parameters.permute_presolve_constraint_order=True;solver.parameters.stop_after_first_solution=True
    if mode==1:solver.parameters.search_branching=cp_model.PORTFOLIO_WITH_QUICK_RESTART_SEARCH
    elif mode==2:solver.parameters.search_branching=cp_model.RANDOMIZED_SEARCH
    elif mode!=0:raise RuntimeError(('mode',mode))
    t=time.time();st=solver.Solve(model);dt=time.time()-t;name=solver.StatusName(st)
    lines=['status='+name,'k=%d'%k,'seed=%d'%seed,'mode=%d'%mode,'sec=%.6f'%dt,'branches=%d'%solver.NumBranches(),'conflicts=%d'%solver.NumConflicts()]
    if st in (cp_model.OPTIMAL,cp_model.FEASIBLE):
        sel=[i for i in range(n) if solver.Value(x[i])]
        if len(sel)!=k or not model_ok(sel,acts,rows) or not direct_ok(P,sel):raise RuntimeError(('verify',len(sel),k))
        N=1
        for i in sel:N*=P[i]
        lines+=['verified=1','indices='+','.join(map(str,sel)),'factors='+','.join(str(P[i]) for i in sel),'N='+str(N)]
        rc=0;print('FOUND k=%d sec=%.3f'%(k,dt))
    else:
        lines+=['verified=0'];rc=2;print('END status=%s k=%d sec=%.3f br=%d cf=%d'%(name,k,dt,solver.NumBranches(),solver.NumConflicts()))
    open(out,'w').write('\n'.join(lines)+'\n');return rc


if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[2]=='check': check(sys.argv[1]); raise SystemExit(0)
    if len(sys.argv) in (6,7): raise SystemExit(solve(sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),float(sys.argv[4]),sys.argv[5],int(sys.argv[6]) if len(sys.argv)==7 else 0))
    raise SystemExit(1)
