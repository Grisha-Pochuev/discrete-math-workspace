#!/usr/bin/env python3
import random,sys,time
import b
from ortools.sat.python import cp_model

def er(m,x,q,a,t,tag):
 v=sorted(a); lo=sum(v[:430]); hi=sum(v[-600:]); zl=max(0,(lo-t+q-1)//q); zh=max(zl,(hi-t)//q)
 z=m.NewIntVar(zl,zh,tag); m.Add(sum(c*x[i] for i,c in enumerate(a) if c)-q*z==t)

def xb(rows,n):
 z=[]
 for q,a,t,_ in rows:
  s=0
  for i,c in enumerate(a):
   if c&1:s|=1<<i
  z.append((s,t&1,None))
 B=b.gf2_rref(z)
 if len(B)!=119:raise RuntimeError(('r',len(B)))
 return [w for _,w in sorted(B.items())]

def ax(m,x,R,k):
 for mask,rhs in R[:k]:
  z=[x[i] for i in range(len(x)) if (mask>>i)&1]
  m.AddBoolXOr(z if rhs else [z[0].Not()]+z[1:])

def tasks(rows,o,seed):
 T=[]
 for r,(q,a,t,_) in enumerate(rows):
  E=q.bit_length()-1
  for e in range(2,E+1):T.append((e,r))
 if len(T)!=123:raise RuntimeError(('l',len(T)))
 rng=random.Random(seed^0x6215a)
 if o==0:T.sort(key=lambda z:(z[0],sum(c!=0 for c in rows[z[1]][1]),z[1]))
 elif o==1:T.sort(key=lambda z:(z[0],-sum(c!=0 for c in rows[z[1]][1]),z[1]))
 else:
  U=[]
  for e in range(2,13):
   g=[z for z in T if z[0]==e];rng.shuffle(g);U+=g
  T=U
 return T

def ver(P,C,S,sol):
 for q,a,t,_ in S:
  if sum(a[i] for i in sol)%q!=t:raise RuntimeError(('s',q))
 N=1
 for i in sol:N*=P[i]
 for i in sol:
  p=P[i]
  if (N-1)%(p-1) or (N+1)%(p+1):raise RuntimeError(('d',i))
 return N

def run(path,seed,sec,out,o,mode,xc,lc):
 P,_,_,_,C,S=b.build(path);n=len(P);O=[z for z in S if z[0]&1];T=[z for z in S if not z[0]&1]
 if len(O)!=194 or len(T)!=120 or any(z[2] for z in O):raise RuntimeError('shape')
 X=xb(T,n);L=tasks(T,o,seed); xs=list(range(xc,119,xc))+[119];ls=list(range(lc,123,lc))+[123]
 ph=[(0,0)]+[(k,0) for k in xs]+[(119,k) for k in ls]
 rng=random.Random(seed^0x6a21);prev=[0]*n
 for i in rng.sample(range(n),515):prev[i]=1
 lines=['seed=%d'%seed,'order=%d'%o,'mode=%d'%mode,'odd=194','xor=119','lift=123','phases=%d'%len(ph)]
 st=time.time();re=-1
 for h,(cx,cl) in enumerate(ph):
  left=sec-time.time()+st
  if left<10:break
  m=cp_model.CpModel();x=[m.NewBoolVar('x%d'%i) for i in range(n)];k=m.NewIntVar(430,600,'k');m.Add(k==sum(x))
  for r,(q,a,t,_) in enumerate(O):
   if mode==1:m.AddModuloEquality(0,sum(c*x[i] for i,c in enumerate(a) if c),q)
   else:er(m,x,q,a,0,'o%d'%r)
  if cx:ax(m,x,X,cx)
  lev=[1]*120
  for e,r in L[:cl]:lev[r]=max(lev[r],e)
  for r,e in enumerate(lev):
   if e<2:continue
   q=1<<e;a=[c%q for c in T[r][1]];t=T[r][2]%q
   if mode==1:m.AddModuloEquality(t,sum(c*x[i] for i,c in enumerate(a) if c),q)
   else:er(m,x,q,a,t,'t%d'%r)
  for i,v in enumerate(prev):m.AddHint(x[i],v)
  m.AddHint(k,sum(prev));sv=cp_model.CpSolver();sv.parameters.max_time_in_seconds=max(20.,left/(len(ph)-h));sv.parameters.num_search_workers=4;sv.parameters.random_seed=seed+1009*h;sv.parameters.randomize_search=True;sv.parameters.permute_variable_randomly=True;sv.parameters.permute_presolve_constraint_order=True;sv.parameters.stop_after_first_solution=True;sv.parameters.repair_hint=True;sv.parameters.hint_conflict_limit=500000
  if mode==2:sv.parameters.search_branching=cp_model.PORTFOLIO_WITH_QUICK_RESTART_SEARCH
  if mode==3:sv.parameters.linearization_level=0;sv.parameters.search_branching=cp_model.PORTFOLIO_WITH_QUICK_RESTART_SEARCH
  t0=time.time();s=sv.Solve(m);dt=time.time()-t0;name=sv.StatusName(s);lines.append('p%d=%s,x=%d,l=%d,sec=%.2f,br=%d,cf=%d'%(h,name,cx,cl,dt,sv.NumBranches(),sv.NumConflicts()))
  if s not in (cp_model.FEASIBLE,cp_model.OPTIMAL):break
  prev=[sv.Value(v) for v in x];re=h
  if cx==119 and cl==123:
   sol=[i for i,v in enumerate(prev) if v];N=ver(P,C,S,sol);lines+=['FOUND','k=%d'%len(sol),'idx='+','.join(map(str,sol)),'fac='+','.join(str(P[i]) for i in sol),'N='+str(N)];open(out,'w').write('\n'.join(lines)+'\n');print('FOUND',len(sol));return 0
 lines+=['OPEN','reached=%d'%re,'sec=%.2f'%(time.time()-st)];open(out,'w').write('\n'.join(lines)+'\n');print('END',re);return 2

if __name__=='__main__':
 if len(sys.argv)!=9:raise SystemExit(1)
 raise SystemExit(run(sys.argv[1],int(sys.argv[2]),float(sys.argv[3]),sys.argv[4],int(sys.argv[5]),int(sys.argv[6]),int(sys.argv[7]),int(sys.argv[8])))
