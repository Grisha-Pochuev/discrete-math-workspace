#!/usr/bin/env python3
import base64,math,random,sys,time
import b
from ortools.sat.python import cp_model
X0='d44URnL9S9yd61Os1+TAV0Zu38yOhhoVEFOVbCGS+Ch6bcokX5xmNCIe8xvd8/PKDqulUgYy/wg4QhyLLx6fGjdZxFioKyi3dtH9j2tQaNkbaOuFIWUE2K30otK0Kw3H1+rcBvfuDHtmRrfvYjmvcpqUNcNfRTaCPmIOuFllI6IY'
def pp(q,p):
 z=q
 while z%p==0:z//=p
 return z==1
def vec(n):
 z=base64.b64decode(X0);x=[(z[i>>3]>>(i&7))&1 for i in range(n)]
 if sum(x)!=521:raise RuntimeError(sum(x))
 return x
def addrow(m,x,W,O,x0,row,tag):
 q,a,t,_=row;aa=[a[i] for i in W];rhs=(t-sum(a[i]*x0[i] for i in O))%q
 hi=sum(aa);zl=(-rhs+q-1)//q;zh=(hi-rhs)//q
 if zl>zh:m.AddBoolOr([]);return
 z=m.NewIntVar(zl,zh,tag);m.Add(sum(c*x[j] for j,c in enumerate(aa) if c)-q*z==rhs)
def score(rows,y):
 e=0;bits=0.
 for q,a,t,_ in rows:
  if sum(a[i] for i,v in enumerate(y) if v)%q==t:e+=1;bits+=math.log2(q)
 return e,bits
def run(path,seed,seconds,out,w,dmin,dmax,mode,tries):
 P,_,_,_,_,S=b.build(path);n=len(P);x0=vec(n);R3=[z for z in S if z[0]&1 and pp(z[0],3)];R5=[z for z in S if z[0]&1 and pp(z[0],5)]
 if len(R3)!=57 or len(R5)!=29:raise RuntimeError('rows')
 rng=random.Random(seed);W=sorted(rng.sample(range(n),min(w,n)));ws=set(W);O=[i for i in range(n) if i not in ws]
 st=time.time();L=['seed=%d'%seed,'w=%d'%len(W),'dmin=%d'%dmin,'dmax=%d'%dmax,'mode=%d'%mode,'tries=%d'%tries];best=None
 for at in range(tries):
  left=seconds-(time.time()-st)
  if left<5:break
  m=cp_model.CpModel();x=[m.NewBoolVar('x%d'%i) for i in W]
  for r,row in enumerate(R3):addrow(m,x,W,O,x0,row,'z%d'%r)
  diff=[x[j] if not x0[i] else x[j].Not() for j,i in enumerate(W)];m.Add(sum(diff)>=dmin)
  if dmax>0:m.Add(sum(diff)<=dmax)
  rr=random.Random(seed+10007*at)
  if mode==1:m.Maximize(sum(rr.randrange(-100000,100001)*x[j] for j in range(len(W))))
  elif mode==2:m.Minimize(sum(diff))
  elif mode==3:
   for j in rr.sample(range(len(W)),min(max(1,dmin//2),len(W))):m.Add(x[j]!=x0[W[j]])
  elif mode==4:m.Maximize(sum((1 if rr.getrandbits(1) else -1)*x[j] for j in range(len(W))))
  elif mode!=0:raise RuntimeError(mode)
  for j,i in enumerate(W):m.AddHint(x[j],x0[i])
  sv=cp_model.CpSolver();sv.parameters.max_time_in_seconds=max(3.,left/(tries-at));sv.parameters.num_search_workers=4;sv.parameters.random_seed=seed+1009*at;sv.parameters.randomize_search=True;sv.parameters.permute_variable_randomly=True;sv.parameters.permute_presolve_constraint_order=True;sv.parameters.repair_hint=True;sv.parameters.hint_conflict_limit=1000000;sv.parameters.stop_after_first_solution=(mode in (0,3))
  if mode==4:sv.parameters.search_branching=cp_model.PORTFOLIO_WITH_QUICK_RESTART_SEARCH
  t0=time.time();ss=sv.Solve(m);dt=time.time()-t0;name=sv.StatusName(ss);L.append('a%d=%s,sec=%.2f,br=%d,cf=%d'%(at,name,dt,sv.NumBranches(),sv.NumConflicts()))
  if ss not in (cp_model.FEASIBLE,cp_model.OPTIMAL):continue
  y=x0[:]
  for j,i in enumerate(W):y[i]=sv.Value(x[j])
  sel=[i for i,v in enumerate(y) if v];dd=sum(a!=bb for a,bb in zip(x0,y))
  if dd<dmin or (dmax>0 and dd>dmax) or not all(sum(a[i] for i in sel)%q==t for q,a,t,_ in R3):raise RuntimeError(('verify',dd))
  e,bits=score(R5,y);L.append('hit=%d,diff=%d,k=%d,p5=%d,bb=%.3f'%(at,dd,len(sel),e,bits))
  if best is None or (bits,e)>(best[0],best[1]):best=(bits,e,y,dd)
 if best:
  bits,e,y,dd=best;z=bytearray((n+7)//8)
  for i,v in enumerate(y):
   if v:z[i>>3]|=1<<(i&7)
  L+=['FOUND','diff=%d'%dd,'k=%d'%sum(y),'p5=%d'%e,'p5bits=%.6f'%bits,'bits='+base64.b64encode(z).decode(),'indices='+','.join(str(i) for i,v in enumerate(y) if v)]
  open(out,'w').write('\n'.join(L)+'\n');print('FOUND',dd,e,bits);return 0
 L+=['OPEN','sec=%.2f'%(time.time()-st)];open(out,'w').write('\n'.join(L)+'\n');print('OPEN');return 2
if __name__=='__main__':
 if len(sys.argv)!=10:raise SystemExit(1)
 raise SystemExit(run(sys.argv[1],int(sys.argv[2]),float(sys.argv[3]),sys.argv[4],int(sys.argv[5]),int(sys.argv[6]),int(sys.argv[7]),int(sys.argv[8]),int(sys.argv[9])))
