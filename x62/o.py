#!/usr/bin/env python3
import base64, random, sys, time
import b
from ortools.sat.python import cp_model
X0='NzNR/koBLPR3Ehd+FNSqOQpI3haHo6pNmXyJb2MmIduX0kNGynjdFDdDm8CJuSepuhgkAHJzF+6LJL02+jijGCbRrJVTlClcwx3t0kC7rGGMF+dW3gLYLWU9rSJgfmNx0VszsfJMTarMx74XzXcJjA8Ws7VJ99cQ1MbS2rvP330b'
def pb(q):
 for p in range(2,int(q**.5)+2):
  if q%p==0:
   z=q
   while z%p==0:z//=p
   if z==1:return p
 return q
def ep(q,p):
 e=0
 while q>1:
  if q%p:raise RuntimeError(('pow',q,p))
  q//=p;e+=1
 return e
def seedvec(n):
 z=base64.b64decode(X0);x=[(z[i>>3]>>(i&7))&1 for i in range(n)]
 if sum(x)!=519:raise RuntimeError(('seed',sum(x)))
 return x
def addrow(m,v,x0,row,mod,d,tag):
 _,aa0,target,_=row;aa=[a%mod for a in aa0];cur=sum(aa[i] for i,z in enumerate(x0) if z)%mod;rhs=(target-cur)%mod
 c=[(-aa[i])%mod if x0[i] else aa[i] for i in range(len(x0))];s=sorted(c);lo=sum(s[:d]);hi=sum(s[-d:]);zl=(lo-rhs+mod-1)//mod;zh=(hi-rhs)//mod
 if zl>zh:m.AddBoolOr([]);return
 z=m.NewIntVar(zl,zh,tag);m.Add(sum(c[i]*v[i] for i in range(len(v)) if c[i])-mod*z==rhs)
def verify(r3,r5,lev,x):
 sel=[i for i,z in enumerate(x) if z]
 for q,a,t,m in r3:
  if sum(a[i] for i in sel)%q!=t:raise RuntimeError(('v3',q,m))
 for ri,e in enumerate(lev):
  if e:
   q,a,t,m=r5[ri];z=5**e
   if sum((a[i]%z) for i in sel)%z!=t%z:raise RuntimeError(('v5',ri,e,q,m))
def run(path,seed,seconds,out,d,style,mode,batch):
 P,_,_,_,_,S=b.build(path);n=len(P);x0=seedvec(n);r3=[z for z in S if z[0]&1 and pb(z[0])==3];r5=[z for z in S if z[0]&1 and pb(z[0])==5]
 if len(r3)!=57 or len(r5)!=29 or d%2:raise RuntimeError(('arg',len(r3),len(r5),d))
 lev=[];tasks=[];sel0=[i for i,z in enumerate(x0) if z]
 for ri,(q,a,t,m) in enumerate(r5):
  E=ep(q,5);delta=sum(a[i] for i in sel0)-t;z=0
  for e in range(1,E+1):
   if delta%(5**e)==0:z=e
   else:break
  lev.append(z)
  for e in range(z+1,E+1):tasks.append((e,ri))
 if sum(lev)!=16 or len(tasks)!=22:raise RuntimeError(('digits',sum(lev),len(tasks)))
 rng=random.Random(seed^0x51962540);nz=lambda z:sum(v!=0 for v in r5[z[1]][1])
 if style==0:tasks.sort(key=lambda z:(z[0],nz(z),z[1]))
 elif style==1:tasks.sort(key=lambda z:(z[0],-nz(z),z[1]))
 elif style==2:rng.shuffle(tasks)
 elif style==3:tasks.sort(key=lambda z:(-z[0],nz(z),z[1]))
 elif style==4:
  g={}
  for z in tasks:g.setdefault(z[0],[]).append(z)
  tasks=[]
  for e in sorted(g):
   a=sorted(g[e],key=nz)
   while a:
    tasks.append(a.pop(0))
    if a:tasks.append(a.pop())
 else:raise RuntimeError(style)
 cuts=list(range(0,len(tasks),batch))+[len(tasks)];prev=[0]*n
 for i in rng.sample(range(n),d):prev[i]=1
 st=time.time();L=['seed=%d'%seed,'d=%d'%d,'style=%d'%style,'mode=%d'%mode,'batch=%d'%batch,'base=%d'%sum(lev),'tasks=%d'%len(tasks),'phases=%d'%len(cuts)]
 def emit(last=True):open(out,'w').write('\n'.join(L+([] if not last else ['last='+','.join(str(i) for i,z in enumerate(prev) if z)]))+'\n')
 emit();at=0;re=-1
 for ph,cut in enumerate(cuts):
  while at<cut:
   e,ri=tasks[at];lev[ri]=max(lev[ri],e);at+=1
  left=seconds-(time.time()-st)
  if left<8:break
  m=cp_model.CpModel();v=[m.NewBoolVar('v%d'%i) for i in range(n)];m.Add(sum(v)==d)
  for ri,row in enumerate(r3):addrow(m,v,x0,row,row[0],d,'a%d'%ri)
  for ri,e in enumerate(lev):
   if e:addrow(m,v,x0,r5[ri],5**e,d,'b%d'%ri)
  if mode in (5,6) and ph:m.Minimize(sum(v[i].Not() if prev[i] else v[i] for i in range(n)))
  for i,z in enumerate(prev):m.AddHint(v[i],z)
  sv=cp_model.CpSolver();sv.parameters.max_time_in_seconds=max(15.,left/(len(cuts)-ph));sv.parameters.num_search_workers=4;sv.parameters.random_seed=seed+1009*ph;sv.parameters.randomize_search=True;sv.parameters.permute_variable_randomly=True;sv.parameters.permute_presolve_constraint_order=True;sv.parameters.repair_hint=True;sv.parameters.hint_conflict_limit=2000000;sv.parameters.stop_after_first_solution=mode not in (5,6)
  if mode in (1,5):sv.parameters.search_branching=cp_model.PORTFOLIO_WITH_QUICK_RESTART_SEARCH
  elif mode==2:sv.parameters.linearization_level=0;sv.parameters.search_branching=cp_model.PORTFOLIO_WITH_QUICK_RESTART_SEARCH
  elif mode==3:sv.parameters.use_ls_only=True;sv.parameters.use_feasibility_jump=True
  elif mode==4:sv.parameters.search_branching=cp_model.RANDOMIZED_SEARCH
  elif mode==6:sv.parameters.linearization_level=0;sv.parameters.search_branching=cp_model.PORTFOLIO_WITH_QUICK_RESTART_SEARCH
  elif mode!=0:raise RuntimeError(mode)
  t0=time.time();ss=sv.Solve(m);dt=time.time()-t0;name=sv.StatusName(ss);L.append('p%d=%s,c=%d,b=%d,sec=%.2f,br=%d,cf=%d'%(ph,name,cut,sum(lev),dt,sv.NumBranches(),sv.NumConflicts()));emit()
  if ss not in (cp_model.FEASIBLE,cp_model.OPTIMAL):break
  prev=[sv.Value(z) for z in v];re=ph;x=[x0[i]^prev[i] for i in range(n)]
  if sum(x)%2!=1 or sum(prev)!=d:raise RuntimeError(('parity',sum(x),sum(prev)))
  verify(r3,r5,lev,x);emit()
  if cut==len(tasks):
   sel=[i for i,z in enumerate(x) if z];bb=bytearray((n+7)//8)
   for i in sel:bb[i>>3]|=1<<(i&7)
   L+=['FOUND','verified=1','k=%d'%len(sel),'diff=%d'%d,'bits='+base64.b64encode(bb).decode(),'indices='+','.join(map(str,sel))];emit(False);print('FOUND',d,len(sel));return 0
 L+=['OPEN','reached=%d'%re,'sec=%.2f'%(time.time()-st)];emit();print('OPEN',re);return 2
if __name__=='__main__':
 if len(sys.argv)!=9:raise SystemExit(1)
 raise SystemExit(run(sys.argv[1],int(sys.argv[2]),float(sys.argv[3]),sys.argv[4],int(sys.argv[5]),int(sys.argv[6]),int(sys.argv[7]),int(sys.argv[8])))
