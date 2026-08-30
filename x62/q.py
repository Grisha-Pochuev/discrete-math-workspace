#!/usr/bin/env python3
import math,random,sys,time
import b
from ortools.sat.python import cp_model

def pbase(q):
    for p in range(3,int(q**.5)+2,2):
        if q%p==0:
            z=q
            while z%p==0:z//=p
            if z==1:return p
    return q

def logball(n,k,t):
    return (math.lgamma(k+1)-math.lgamma(t+1)-math.lgamma(k-t+1)+math.lgamma(n-k+1)-math.lgamma(t+1)-math.lgamma(n-k-t+1))/math.log(2)

def rows(S,style,seed):
    R=[z for z in S if z[0]&1];rng=random.Random(seed^0x71a62)
    if style==0:R.sort(key=lambda z:(pbase(z[0]),z[0],sum(v!=0 for v in z[1])))
    elif style==1:R.sort(key=lambda z:(z[0],pbase(z[0]),sum(v!=0 for v in z[1])))
    elif style==2:R.sort(key=lambda z:(-math.log2(z[0]),sum(v!=0 for v in z[1])))
    elif style==3:rng.shuffle(R)
    elif style==4:R.sort(key=lambda z:(sum(v!=0 for v in z[1]),z[0]))
    else:raise RuntimeError(style)
    return R

def batches(R,bits):
    B=[];cur=[];w=0.
    for z in R:
        v=math.log2(z[0])
        if cur and w+v>bits*1.25:B.append(cur);cur=[];w=0.
        cur.append(z);w+=v
        if w>=bits:B.append(cur);cur=[];w=0.
    if cur:B.append(cur)
    return B

def er(m,x,row,k,tag):
    q,a,t,_=row;s=sorted(a);lo=sum(s[:k]);hi=sum(s[-k:]);zl=(lo-t+q-1)//q;zh=(hi-t)//q
    z=m.NewIntVar(zl,zh,tag);m.Add(sum(c*x[i] for i,c in enumerate(a) if c)-q*z==t)

def verify(S,sol,R):
    for q,a,t,_ in R:
        if sum(a[i] for i in sol)%q!=t:return False
    return True

def emit(path,L,prev):
    z=list(L)
    if prev is not None:z.append('last='+','.join(str(i) for i,v in enumerate(prev) if v))
    open(path,'w').write('\n'.join(z)+'\n')

def run(path,seed,seconds,out,k,style,mode,bbits,margin):
    P,_,_,_,_,S=b.build(path);n=len(P);R=rows(S,style,seed);B=batches(R,bbits);rng=random.Random(seed)
    prev=[0]*n
    for i in rng.sample(range(n),k):prev[i]=1
    L=['seed=%d'%seed,'k=%d'%k,'style=%d'%style,'mode=%d'%mode,'bb=%.1f'%bbits,'margin=%.1f'%margin,'rows=%d'%len(R),'phases=%d'%len(B)];emit(out,L,prev)
    active=[];cum=0.;st=time.time();re=-1
    for ph,add in enumerate(B):
        active+=add;cum+=sum(math.log2(z[0]) for z in add);left=seconds-(time.time()-st)
        if left<12:break
        t=1
        while t<min(k,n-k) and logball(n,k,t)<cum+margin:t+=1
        ok=False
        for att,extra in enumerate((0,max(4,int(.12*t)+3))):
            left=seconds-(time.time()-st)
            if left<10:break
            rad=min(min(k,n-k),t+extra)
            m=cp_model.CpModel();x=[m.NewBoolVar('x%d'%i) for i in range(n)];m.Add(sum(x)==k)
            for ri,row in enumerate(active):er(m,x,row,k,'z%d'%ri)
            diff=[x[i] if not prev[i] else x[i].Not() for i in range(n)]
            m.Add(sum(diff)<=2*rad)
            for i,v in enumerate(prev):m.AddHint(x[i],v)
            sv=cp_model.CpSolver();remaining=len(B)-ph
            budget=min(left-5.,max(22.,left/(remaining+0.35)*(1.0 if att==0 else .7)))
            sv.parameters.max_time_in_seconds=budget;sv.parameters.num_search_workers=4;sv.parameters.random_seed=seed+1009*ph+97*att
            sv.parameters.randomize_search=True;sv.parameters.permute_variable_randomly=True;sv.parameters.permute_presolve_constraint_order=True;sv.parameters.stop_after_first_solution=True;sv.parameters.repair_hint=True;sv.parameters.hint_conflict_limit=2000000
            if mode==1:sv.parameters.search_branching=cp_model.PORTFOLIO_WITH_QUICK_RESTART_SEARCH
            elif mode==2:sv.parameters.linearization_level=0;sv.parameters.search_branching=cp_model.PORTFOLIO_WITH_QUICK_RESTART_SEARCH
            elif mode==3:sv.parameters.search_branching=cp_model.FIXED_SEARCH;m.AddDecisionStrategy(x,cp_model.CHOOSE_HIGHEST_MAX,cp_model.SELECT_MIN_VALUE)
            elif mode!=0:raise RuntimeError(mode)
            t0=time.time();ss=sv.Solve(m);dt=time.time()-t0;name=sv.StatusName(ss)
            L.append('p%d.a%d=%s,r=%d,b=%.2f,sec=%.2f,br=%d,cf=%d'%(ph,att,name,rad,cum,dt,sv.NumBranches(),sv.NumConflicts()));emit(out,L,prev)
            if ss in (cp_model.FEASIBLE,cp_model.OPTIMAL):
                z=[sv.Value(v) for v in x];sol=[i for i,v in enumerate(z) if v]
                if len(sol)!=k or not verify(S,sol,active):raise RuntimeError(('verify',ph))
                prev=z;re=ph;ok=True;emit(out,L,prev);break
        if not ok:break
    sol=[i for i,v in enumerate(prev) if v]
    if re==len(B)-1 and verify(S,sol,R):
        L+=['FOUND','verified=1','fac='+','.join(str(P[i]) for i in sol)];emit(out,L,prev);print('FOUND',len(sol));return 0
    L+=['OPEN','reached=%d'%re,'bits=%.3f'%sum(sum(math.log2(z[0]) for z in B[j]) for j in range(re+1)),'sec=%.2f'%(time.time()-st)];emit(out,L,prev);print('END',re);return 2
if __name__=='__main__':
    if len(sys.argv)!=10:raise SystemExit(1)
    raise SystemExit(run(sys.argv[1],int(sys.argv[2]),float(sys.argv[3]),sys.argv[4],int(sys.argv[5]),int(sys.argv[6]),int(sys.argv[7]),float(sys.argv[8]),float(sys.argv[9])))
