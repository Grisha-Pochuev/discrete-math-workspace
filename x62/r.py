#!/usr/bin/env python3
import base64,math,random,sys,time
import b
from ortools.sat.python import cp_model
X0='d44URnL9S9yd61Os1+TAV0Zu38yOhhoVEFOVbCGS+Ch6bcokX5xmNCIe8xvd8/PKDqulUgYy/wg4QhyLLx6fGjdZxFioKyi3dtH9j2tQaNkbaOuFIWUE2K30otK0Kw3H1+rcBvfuDHtmRrfvYjmvcpqUNcNfRTaCPmIOuFllI6IY'
def pb(q):
 for p in range(2,int(q**.5)+2):
  if q%p==0:
   z=q
   while z%p==0:z//=p
   if z==1:return p
 return q
def xbase(n):
 z=base64.b64decode(X0);x=[(z[i>>3]>>(i&7))&1 for i in range(n)]
 if sum(x)!=521:raise RuntimeError(sum(x))
 return x
def crt(rr,n):
 Q=math.prod(z[0] for z in rr);a=[0]*n;t=0
 for q,c,b0,_ in rr:
  u=Q//q;w=u*pow(u,-1,q);t=(t+b0*w)%Q
  for i,v in enumerate(c):a[i]=(a[i]+v*w)%Q
 return Q,a,t,None
def pack(rows,n):
 G={}
 for z in rows:G.setdefault(pb(z[0]),[]).append(z)
 R=max(map(len,G.values()));B=[[] for _ in range(R)];L=[0.]*R
 for p,rr in sorted(G.items(),key=lambda z:-sum(math.log2(x[0]) for x in z[1])):
  jj=sorted(range(R),key=lambda j:L[j])[:len(rr)]
  for j,z in zip(jj,sorted(rr,key=lambda x:-x[0])):B[j].append(z);L[j]+=math.log2(z[0])
 return [crt(z,n) for z in B]
def addrow(m,v,rem,add,x0,row,t,tag):
 q,a,target,_=row;cur=sum(a[i] for i,z in enumerate(x0) if z)%q;rhs=(target-cur)%q
 ar=[(-a[i])%q for i in rem];aa=[a[i]%q for i in add];vals=sorted(ar);vals2=sorted(aa);lo=sum(vals[:t])+sum(vals2[:t]);hi=sum(vals[-t:])+sum(vals2[-t:]);zl=(lo-rhs+q-1)//q;zh=(hi-rhs)//q
 if zl>zh:m.AddBoolOr([]);return
 z=m.NewIntVar(zl,zh,tag);m.Add(sum(ar[j]*v[j] for j in range(len(rem)) if ar[j])+sum(aa[j]*v[len(rem)+j] for j in range(len(add)) if aa[j])-q*z==rhs)
def verify(rows,x):
 s=[i for i,z in enumerate(x) if z]
 return all(sum(a[i] for i in s)%q==t for q,a,t,_ in rows)
def run(path,seed,seconds,out,t,style,mode,batch,form):
 P,_,_,_,_,S=b.build(path);n=len(P);x0=xbase(n);rem=[i for i,z in enumerate(x0) if z];add=[i for i,z in enumerate(x0) if not z];R3=[z for z in S if z[0]&1 and pb(z[0])==3];R5=[z for z in S if z[0]&1 and pb(z[0])==5]
 if len(R3)!=57 or len(R5)!=29:raise RuntimeError(('rows',len(R3),len(R5)))
 rng=random.Random(seed)
 if style==0:R5.sort(key=lambda z:(z[0],sum(c!=0 for c in z[1])))
 elif style==1:R5.sort(key=lambda z:(-z[0],sum(c!=0 for c in z[1])))
 elif style==2:rng.shuffle(R5)
 elif style==3:R5.sort(key=lambda z:(sum(c!=0 for c in z[1]),z[0]))
 else:raise RuntimeError(style)
 cuts=list(range(0,len(R5),batch))+[len(R5)]
 if cuts[0]!=0:cuts=[0]+cuts
 prev=[0]*(len(rem)+len(add))
 for j in rng.sample(range(len(rem)),t):prev[j]=1
 for j in rng.sample(range(len(add)),t):prev[len(rem)+j]=1
 st=time.time();L=['seed=%d'%seed,'t=%d'%t,'style=%d'%style,'mode=%d'%mode,'batch=%d'%batch,'form=%d'%form,'r3=%d'%len(R3),'r5=%d'%len(R5),'phases=%d'%len(cuts)]
 def emit():open(out,'w').write('\n'.join(L+['last='+','.join(str(i) for i,z in enumerate(prev) if z)])+'\n')
 emit();re=-1
 for ph,cut in enumerate(cuts):
  left=seconds-(time.time()-st)
  if left<8:break
  rows=R3+R5[:cut]
  if form:rows=pack(rows,n)
  m=cp_model.CpModel();v=[m.NewBoolVar('v%d'%i) for i in range(len(prev))];m.Add(sum(v[:len(rem)])==t);m.Add(sum(v[len(rem):])==t)
  for ri,row in enumerate(rows):addrow(m,v,rem,add,x0,row,t,'z%d'%ri)
  for i,z in enumerate(prev):m.AddHint(v[i],z)
  sv=cp_model.CpSolver();budget=max(12.,left/(len(cuts)-ph));sv.parameters.max_time_in_seconds=float(budget);sv.parameters.num_search_workers=4;sv.parameters.random_seed=seed+1009*ph;sv.parameters.randomize_search=True;sv.parameters.permute_variable_randomly=True;sv.parameters.permute_presolve_constraint_order=True;sv.parameters.stop_after_first_solution=True;sv.parameters.repair_hint=True;sv.parameters.hint_conflict_limit=2000000
  if mode==1:sv.parameters.search_branching=cp_model.PORTFOLIO_WITH_QUICK_RESTART_SEARCH
  elif mode==2:sv.parameters.linearization_level=0;sv.parameters.search_branching=cp_model.PORTFOLIO_WITH_QUICK_RESTART_SEARCH
  elif mode==3:sv.parameters.use_ls_only=True;sv.parameters.use_feasibility_jump=True
  elif mode==4:sv.parameters.search_branching=cp_model.RANDOMIZED_SEARCH
  elif mode!=0:raise RuntimeError(mode)
  z0=time.time();ss=sv.Solve(m);dt=time.time()-z0;name=sv.StatusName(ss);L.append('p%d=%s,c=%d,r=%d,sec=%.2f,br=%d,cf=%d'%(ph,name,cut,len(rows),dt,sv.NumBranches(),sv.NumConflicts()));emit()
  if ss not in (cp_model.FEASIBLE,cp_model.OPTIMAL):break
  prev=[sv.Value(z) for z in v];re=ph
  x=x0[:]
  for j,i in enumerate(rem):
   if prev[j]:x[i]=0
  for j,i in enumerate(add):
   if prev[len(rem)+j]:x[i]=1
  if sum(x)!=521 or not verify(R3+R5[:cut],x):raise RuntimeError(('verify',ph,cut))
  emit()
  if cut==len(R5):
   sel=[i for i,z in enumerate(x) if z];bb=bytearray((n+7)//8)
   for i in sel:bb[i>>3]|=1<<(i&7)
   L+=['FOUND','verified=1','k=%d'%len(sel),'diff=%d'%(2*t),'bits='+base64.b64encode(bb).decode(),'indices='+','.join(map(str,sel))];open(out,'w').write('\n'.join(L)+'\n');print('FOUND',t);return 0
 L+=['OPEN','reached=%d'%re,'sec=%.2f'%(time.time()-st)];emit();print('OPEN',re);return 2
if __name__=='__main__':
 if len(sys.argv)!=10:raise SystemExit(1)
 raise SystemExit(run(sys.argv[1],int(sys.argv[2]),float(sys.argv[3]),sys.argv[4],int(sys.argv[5]),int(sys.argv[6]),int(sys.argv[7]),int(sys.argv[8]),int(sys.argv[9])))
