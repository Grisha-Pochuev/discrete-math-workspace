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

def order_rows(S,style,seed):
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

def xbasis(coords,n):
    B=b.gf2_rref(b.gf2_rows(coords,n))
    if len(B)!=119:raise RuntimeError(('rank',len(B)))
    return [z for _,z in sorted(B.items())],B

def addxor(m,x,R):
    for mask,rhs in R:
        v=[x[i] for i in range(len(x)) if (mask>>i)&1]
        m.AddBoolXOr(v if rhs else [v[0].Not()]+v[1:])

def xhint(B,n,k,seed):
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
    for _ in range(30000):
        w=part
        for mv in moves:
            if rng.getrandbits(1):w^=mv
        d=abs(w.bit_count()-k)
        if d<bd:best,bd=w,d
        if d==0:break
    if bd:raise RuntimeError(('hintk',best.bit_count(),k))
    return [(best>>i)&1 for i in range(n)]

def lift_tasks(two,style,seed):
    T=[]
    for r,(q,a,t,meta) in enumerate(two):
        E=q.bit_length()-1
        for e in range(2,E+1):T.append((e,r))
    if len(T)!=123:raise RuntimeError(('lift',len(T)))
    rng=random.Random(seed^0x2ad1)
    if style==0:T.sort(key=lambda z:(z[0],sum(v!=0 for v in two[z[1]][1]),z[1]))
    elif style==1:T.sort(key=lambda z:(z[0],-sum(v!=0 for v in two[z[1]][1]),z[1]))
    elif style==2:T.sort(key=lambda z:(-z[0],sum(v!=0 for v in two[z[1]][1]),z[1]))
    else:rng.shuffle(T)
    return T

def check_rows(sol,R):
    return all(sum(a[i] for i in sol)%q==t for q,a,t,_ in R)

def check_x(sol,X):
    s=set(sol)
    return all((sum(1 for i in s if (mask>>i)&1)&1)==rhs for mask,rhs in X)

def emit(path,L,prev):
    z=list(L)
    if prev is not None:z.append('last='+','.join(str(i) for i,v in enumerate(prev) if v))
    open(path,'w').write('\n'.join(z)+'\n')

def configure(sv,mode,seed):
    sv.parameters.num_search_workers=4;sv.parameters.random_seed=seed;sv.parameters.randomize_search=True
    sv.parameters.permute_variable_randomly=True;sv.parameters.permute_presolve_constraint_order=True
    sv.parameters.stop_after_first_solution=True;sv.parameters.repair_hint=True;sv.parameters.hint_conflict_limit=3000000
    if mode==1:sv.parameters.search_branching=cp_model.PORTFOLIO_WITH_QUICK_RESTART_SEARCH
    elif mode==2:sv.parameters.linearization_level=0;sv.parameters.search_branching=cp_model.PORTFOLIO_WITH_QUICK_RESTART_SEARCH
    elif mode==3:sv.parameters.use_ls_only=True;sv.parameters.use_feasibility_jump=True
    elif mode!=0:raise RuntimeError(mode)

def run(path,seed,seconds,out,k,style,mode,bbits,margin,lbatch):
    P,F,M,T,C,S=b.build(path);n=len(P);O=order_rows(S,style,seed);OB=batches(O,bbits)
    X,B=xbasis(C,n);two=[z for z in S if not(z[0]&1)];LT=lift_tasks(two,style%4,seed)
    prev=xhint(B,n,k,seed);L=['seed=%d'%seed,'k=%d'%k,'style=%d'%style,'mode=%d'%mode,'bb=%.1f'%bbits,'margin=%.1f'%margin,'odd=%d'%len(O),'ob=%d'%len(OB),'xor=%d'%len(X),'lift=%d'%len(LT)];emit(out,L,prev)
    active=[];cum=0.;lev=[1]*len(two);st=time.time();re=-1;fullodd=False
    phases=[('o',z) for z in OB]+[('l',LT[i:i+lbatch]) for i in range(0,len(LT),lbatch)]
    for ph,(kind,add) in enumerate(phases):
        if kind=='o':
            active+=add;cum+=sum(math.log2(z[0]) for z in add)
        else:
            for e,r in add:lev[r]=max(lev[r],e);cum+=1
        left=seconds-(time.time()-st)
        if left<14:break
        req=119+cum+margin;t=1
        while t<min(k,n-k) and logball(n,k,t)<req:t+=1
        ok=False
        for att,extra in enumerate((0,max(5,int(.10*t)+4),max(12,int(.25*t)+8))):
            left=seconds-(time.time()-st)
            if left<12:break
            rad=min(min(k,n-k),t+extra)
            m=cp_model.CpModel();x=[m.NewBoolVar('x%d'%i) for i in range(n)];m.Add(sum(x)==k);addxor(m,x,X)
            for ri,row in enumerate(active):er(m,x,row,k,'o%d'%ri)
            for r,e in enumerate(lev):
                if e<2:continue
                q=1<<e;q0,a0,t0,_=two[r];row=(q,[v%q for v in a0],t0%q,None);er(m,x,row,k,'t%d'%r)
            if att<2:
                diff=[x[i] if not prev[i] else x[i].Not() for i in range(n)];m.Add(sum(diff)<=2*rad)
            for i,v in enumerate(prev):m.AddHint(x[i],v)
            sv=cp_model.CpSolver();remaining=len(phases)-ph;budget=min(left-5.,max(25.,left/(remaining+.25)*(1.0 if att==0 else .75)))
            sv.parameters.max_time_in_seconds=budget;configure(sv,mode,seed+1009*ph+97*att)
            t0s=time.time();ss=sv.Solve(m);dt=time.time()-t0s;name=sv.StatusName(ss)
            L.append('p%d.%d=%s,kd=%s,r=%d,b=%.2f,sec=%.2f,br=%d,cf=%d'%(ph,att,name,kind,rad,cum,dt,sv.NumBranches(),sv.NumConflicts()));emit(out,L,prev)
            if ss in (cp_model.FEASIBLE,cp_model.OPTIMAL):
                z=[sv.Value(v) for v in x];sol=[i for i,v in enumerate(z) if v]
                if len(sol)!=k or not check_x(sol,X) or not check_rows(sol,active):raise RuntimeError(('verify',ph))
                for r,e in enumerate(lev):
                    if e>=2:
                        q=1<<e;q0,a0,t0,_=two[r]
                        if sum(a0[i] for i in sol)%q!=t0%q:raise RuntimeError(('liftverify',r,e))
                prev=z;re=ph;ok=True;emit(out,L,prev);break
        if not ok:break
        if kind=='o' and len(active)==len(O):fullodd=True
    sol=[i for i,v in enumerate(prev) if v]
    if re==len(phases)-1 and check_rows(sol,S):
        N=1
        for i in sol:N*=P[i]
        for i in sol:
            p=P[i]
            if (N-1)%(p-1) or (N+1)%(p+1):raise RuntimeError(('direct',i,p))
        L+=['FOUND','verified=1','fac='+','.join(str(P[i]) for i in sol),'N='+str(N)];emit(out,L,prev);print('FOUND',k);return 0
    L+=['OPEN','reached=%d'%re,'fullodd=%d'%(1 if fullodd else 0),'bits=%.3f'%cum,'sec=%.2f'%(time.time()-st)];emit(out,L,prev);print('END',re,fullodd,cum);return 2
if __name__=='__main__':
    if len(sys.argv)!=11:raise SystemExit(1)
    raise SystemExit(run(sys.argv[1],int(sys.argv[2]),float(sys.argv[3]),sys.argv[4],int(sys.argv[5]),int(sys.argv[6]),int(sys.argv[7]),float(sys.argv[8]),float(sys.argv[9]),int(sys.argv[10])))
