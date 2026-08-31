#!/usr/bin/env python3
import base64,math,random,sys,time
import b
from ortools.sat.python import cp_model

X0='d44URnL9S9yd61Os1+TAV0Zu38yOhhoVEFOVbCGS+Ch6bcokX5xmNCIe8xvd8/PKDqulUgYy/wg4QhyLLx6fGjdZxFioKyi3dtH9j2tQaNkbaOuFIWUE2K30otK0Kw3H1+rcBvfuDHtmRrfvYjmvcpqUNcNfRTaCPmIOuFllI6IY'

def ppow(q,p):
 e=0
 while q%p==0:q//=p;e+=1
 return e if q==1 else 0

def initial(n):
 z=base64.b64decode(X0)
 x=[(z[i>>3]>>(i&7))&1 for i in range(n)]
 if sum(x)!=521:raise RuntimeError(('x0',sum(x)))
 return x

def order_tasks(rows,x0,style,seed):
 rng=random.Random(seed^0x72535)
 T=[]
 for ri,(q,a,t,m) in enumerate(rows):
  E=ppow(q,5)
  for e in range(1,E+1):T.append((e,ri))
 if sum(ppow(z[0],5) for z in rows)!=38:raise RuntimeError('digits')
 if style==0:T.sort(key=lambda z:(z[0],sum(v!=0 for v in rows[z[1]][1]),z[1]))
 elif style==1:T.sort(key=lambda z:(z[0],-sum(v!=0 for v in rows[z[1]][1]),z[1]))
 elif style==2:rng.shuffle(T)
 elif style==3:
  T=[(ppow(q,5),ri) for ri,(q,a,t,m) in enumerate(rows)]
  T.sort(key=lambda z:(z[0],sum(v!=0 for v in rows[z[1]][1])))
 elif style==4:
  T.sort(key=lambda z:(0 if sum(rows[z[1]][1][i]*x0[i] for i in range(len(x0)))%(5**z[0]) else 1,z[0],z[1]))
 else:raise RuntimeError(('style',style))
 return T

def add_row(model,x,W,O,xout,row,m,tag,k,enc):
 q0,a,t,meta=row;q=m
 aa=[a[i]%q for i in W]
 rhs=(t-sum((a[i]%q)*xout[i] for i in O))%q
 expr=sum(c*x[j] for j,c in enumerate(aa) if c)
 if enc:
  model.AddModuloEquality(rhs,expr,q);return
 vals=sorted(aa);lo=sum(vals[:k]);hi=sum(vals[-k:])
 zl=(lo-rhs+q-1)//q;zh=(hi-rhs)//q
 if zl>zh:model.AddBoolOr([]);return
 z=model.NewIntVar(zl,zh,tag);model.Add(expr-q*z==rhs)

def solve(path,seed,seconds,out,w,style,mode,batch):
 P,_,_,_,_,S=b.build(path);n=len(P);x0=initial(n)
 R3=[z for z in S if ppow(z[0],3)]
 R5=[z for z in S if ppow(z[0],5)]
 if len(R3)!=57 or len(R5)!=29:raise RuntimeError(('rows',len(R3),len(R5)))
 for q,a,t,m in R3:
  if sum(a[i]*x0[i] for i in range(n))%q!=t:raise RuntimeError(('base',q,m))
 rng=random.Random(seed)
 if w<=0 or w>=n:W=list(range(n))
 else:W=sorted(rng.sample(range(n),w))
 ws=set(W);O=[i for i in range(n) if i not in ws];fixed=sum(x0[i] for i in O);k=521-fixed
 if k<0 or k>len(W):raise RuntimeError(('k',k,len(W)))
 T=order_tasks(R5,x0,style,seed);cuts=list(range(batch,len(T),batch))+[len(T)]
 prev=x0[:];levels=[0]*len(R5);start=time.time();lines=['seed=%d'%seed,'w=%d'%len(W),'k=%d'%k,'style=%d'%style,'mode=%d'%mode,'batch=%d'%batch,'p3=%d'%len(R3),'p5=%d'%len(R5),'tasks=%d'%len(T),'phases=%d'%len(cuts)]
 def emit():
  open(out,'w').write('\n'.join(lines+['last='+','.join(str(i) for i,v in enumerate(prev) if v)])+'\n')
 emit();at=0
 for ph,cut in enumerate(cuts):
  while at<cut:
   e,r=T[at];levels[r]=max(levels[r],e);at+=1
  left=seconds-(time.time()-start)
  if left<8:lines.append('p%d=NO_TIME'%ph);break
  model=cp_model.CpModel();x=[model.NewBoolVar('x%d'%i) for i in W];model.Add(sum(x)==k)
  enc=mode in (5,6)
  for ri,row in enumerate(R3):add_row(model,x,W,O,prev,row,row[0],'a%d'%ri,k,enc)
  for ri,e in enumerate(levels):
   if e:add_row(model,x,W,O,prev,R5[ri],5**e,'b%d'%ri,k,enc)
  if mode==1 and ph:
   model.Minimize(sum(x[j].Not() if prev[i] else x[j] for j,i in enumerate(W)))
  for j,i in enumerate(W):model.AddHint(x[j],prev[i])
  sv=cp_model.CpSolver();budget=max(15.,left/(len(cuts)-ph));sv.parameters.max_time_in_seconds=float(budget);sv.parameters.num_search_workers=4
  sv.parameters.random_seed=seed+1009*ph;sv.parameters.randomize_search=True;sv.parameters.permute_variable_randomly=True;sv.parameters.permute_presolve_constraint_order=True;sv.parameters.stop_after_first_solution=True;sv.parameters.repair_hint=True;sv.parameters.hint_conflict_limit=2000000
  if mode==2:sv.parameters.search_branching=cp_model.PORTFOLIO_WITH_QUICK_RESTART_SEARCH
  elif mode==3:sv.parameters.use_ls_only=True;sv.parameters.use_feasibility_jump=True
  elif mode==4:sv.parameters.linearization_level=0;sv.parameters.search_branching=cp_model.PORTFOLIO_WITH_QUICK_RESTART_SEARCH
  elif mode==6:sv.parameters.linearization_level=0
  elif mode not in (0,1,5):raise RuntimeError(('mode',mode))
  t0=time.time();st=sv.Solve(model);dt=time.time()-t0;name=sv.StatusName(st)
  lines.append('p%d=%s,c=%d,r=%d,sec=%.2f,br=%d,cf=%d'%(ph,name,cut,sum(e>0 for e in levels),dt,sv.NumBranches(),sv.NumConflicts()));emit()
  if st not in (cp_model.FEASIBLE,cp_model.OPTIMAL):break
  for j,i in enumerate(W):prev[i]=sv.Value(x[j])
  sel=[i for i,v in enumerate(prev) if v]
  if len(sel)!=521:raise RuntimeError(('weight',len(sel)))
  for q,a,t,m in R3:
   if sum(a[i] for i in sel)%q!=t:raise RuntimeError(('v3',q,m))
  for ri,e in enumerate(levels):
   if e and sum((R5[ri][1][i]%(5**e)) for i in sel)%(5**e)!=R5[ri][2]%(5**e):raise RuntimeError(('v5',ri,e))
  emit()
  if cut==len(T):
   if not all(sum(a[i] for i in sel)%q==t for q,a,t,m in R5):raise RuntimeError('final')
   z=bytearray((n+7)//8)
   for i in sel:z[i>>3]|=1<<(i&7)
   lines+=['FOUND','verified=1','bits='+base64.b64encode(z).decode(),'indices='+','.join(map(str,sel))]
   open(out,'w').write('\n'.join(lines)+'\n');print('FOUND',len(sel),time.time()-start);return 0
 lines+=['OPEN','sec=%.2f'%(time.time()-start)];emit();print('END',lines[-2]);return 2
if __name__=='__main__':
 if len(sys.argv)!=9:raise SystemExit(1)
 raise SystemExit(solve(sys.argv[1],int(sys.argv[2]),float(sys.argv[3]),sys.argv[4],int(sys.argv[5]),int(sys.argv[6]),int(sys.argv[7]),int(sys.argv[8])))
