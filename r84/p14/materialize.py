"""Deterministic input-only diversification. No solver or network."""
import hashlib,json,sys,time,shutil
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];C=ROOT/'p12_collection';GLOBALS=ROOT/'p13_plan/global';OUTROOT=Path(__file__).resolve().parent;EXPECTED_UNIONS={}
def configure(data_root,globals_root,output_root,expected_union_hashes=None):
 global C,GLOBALS,OUTROOT,_GLOBAL_CACHE,EXPECTED_UNIONS
 C,GLOBALS,OUTROOT=map(Path,(data_root,globals_root,output_root));_GLOBAL_CACHE=None;EXPECTED_UNIONS=expected_union_hashes or {}
sys.path.insert(0,str(C/'source/engine'))
import paired_engine as E

def need(x,m):
 if not x:raise ValueError(m)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def edgekeys(t,n):
 b=np.roll(t,-1);return np.sort(np.minimum(t,b)*n+np.maximum(t,b))
def topo(t,n):return hashlib.sha256(edgekeys(t,n).astype('<i8').tobytes()).hexdigest()
def stream(path):
 with open(path) as f:
  h=f.readline().split()
  for _ in range(100):
   nc=f.readline().split();line=f.readline();yield np.fromstring(line,sep=' ',dtype=np.int64)-1
  need(not f.read().strip(),'trailing checkpoint')
def union_inputs(jobs):
 geometries=[]
 for j in jobs:
  path=C/'unpacked'/str(j)/'o/run/00/inputs';meta=json.load(open(path/'context.json'));geometries.append((meta['files']['instance']['sha256'],meta['files']['vertices']['sha256']))
 need(len(set(geometries))==1,'mixed input geometry')
 cache=OUTROOT/f"union_{jobs[0]}.npz";receipt=OUTROOT/f"union_{jobs[0]}.json"
 if cache.exists():
  data=np.load(cache,allow_pickle=False);pins=json.loads(str(data["pins"]));record=json.load(open(receipt));edges=data["edges"]
  need(hashlib.sha256(edges.astype('<i8').tobytes()).hexdigest()==record['edges_sha256'],'cache content hash')
  if str(jobs[0]) in EXPECTED_UNIONS:need(record['edges_sha256']==EXPECTED_UNIONS[str(jobs[0])],'frozen union identity')
  need(pins==record['pins'] and [v['job'] for v in pins]==jobs,'cache source identities')
  for v in pins:
   path=C/'unpacked'/str(v['job'])/'o/run/00/inputs';meta=json.load(open(path/'context.json'));need(sha(path/'context.json')==v['context_sha256'] and sha(path/meta['files']['checkpoint']['file'])==v['checkpoint_sha256'],'cache source changed')
  return edges,pins
 union=set();pins=[];seen=set()
 for j in jobs:
  p=C/'unpacked'/str(j)/'o/run/00/inputs';m=json.load(open(p/'context.json'));cp=p/m['files']['checkpoint']['file'];digest=sha(cp);need(digest==m['files']['checkpoint']['sha256'],'input pin')
  pins.append({'job':j,'checkpoint_sha256':digest,'context_sha256':sha(p/'context.json')})
  if digest in seen:continue
  seen.add(digest)
  for t in stream(cp):union.update(map(int,edgekeys(t,len(t))))
 a=np.array(sorted(union),dtype=np.int64)
 if str(jobs[0]) in EXPECTED_UNIONS:need(hashlib.sha256(a.astype('<i8').tobytes()).hexdigest()==EXPECTED_UNIONS[str(jobs[0])],'frozen union identity')
 np.savez(cache,edges=a,pins=json.dumps(pins));receipt.write_text(json.dumps({'edges_sha256':hashlib.sha256(a.astype('<i8').tobytes()).hexdigest(),'pins':pins},indent=2)+'\n');return a,pins

def candidates(t,inst,support,union,limit=200):
 n=inst.n;pos=np.empty(n,dtype=np.int64);pos[t]=np.arange(n)
 a=np.repeat(support,inst.nn.shape[1]);c=np.asarray(inst.nn[support]).reshape(-1).astype(np.int64)
 ia=pos[a];ic=pos[c];swap=ia>ic
 lo=np.minimum(ia,ic);hi=np.maximum(ia,ic)
 a=t[lo];b=t[(lo+1)%n];c=t[hi];d=t[(hi+1)%n]
 key=lambda u,v:np.minimum(u,v)*n+np.maximum(u,v)
 old1=key(a,b);old2=key(c,d);new1=key(a,c);new2=key(b,d)
 ok=(hi>lo+1)&~((lo==0)&(hi==n-1))&~np.isin(old1,inst.fkeys)&~np.isin(old2,inst.fkeys)
 fresh=(~np.isin(new1,union)).astype(np.int64)+(~np.isin(new2,union)).astype(np.int64)
 ok &= fresh>0
 def dist(u,v):
  z=inst.xyz[u]-inst.xyz[v];return np.floor(np.sqrt(np.sum(z*z,axis=1))+.5).astype(np.int64)
 gain=dist(a,c)+dist(b,d)-dist(a,b)-dist(c,d)
 idx=np.flatnonzero(ok);order=np.lexsort((hi[idx],lo[idx],-fresh[idx],gain[idx]));out=[];seen=set()
 for i in idx[order]:
  cuts=(int(lo[i]),int(hi[i]))
  if cuts in seen:continue
  seen.add(cuts);out.append({'cuts':cuts,'cost_delta':int(gain[i]),'fresh_edges':int(fresh[i]),'removed':[int(old1[i]),int(old2[i])],'added':[int(new1[i]),int(new2[i])]})
  if len(out)>=limit:break
 return out

def apply(t,move):
 lo,hi=move['cuts'];z=t.copy();z[lo+1:hi+1]=z[lo+1:hi+1][::-1];return z

def donors(t,inst,support,union,mode,count=10):
 existing=set();out=[];moves=candidates(t,inst,support,union,500)
 need(len(moves)>=count,'insufficient novel candidates')
 for i in range(count):
  z=t.copy();trail=[]
  if mode=='mild':
   filtered=[mv for mv in moves if mv['fresh_edges']==2];need(len(filtered)>=count,'insufficient two-new-edge mild moves')
   move=filtered[i];z=apply(z,move);trail.append(move)
  elif mode=='strong':
   # Three non-cancelling spatially near candidate reversals, not unrestricted random jumps.
   for depth in range(3):
    choices=candidates(z,inst,support,union,500);chosen=None
    for mv in choices[(7*i+3*depth)%30:]+choices[:(7*i+3*depth)%30]:
     trial=apply(z,mv);fresh=np.setdiff1d(edgekeys(trial,inst.n),union,assume_unique=True)
     if len(fresh)>=2*(depth+1):chosen=(mv,trial);break
    need(chosen is not None,'no non-cancelling strong move');mv,z=chosen;trail.append(mv)
  else:raise ValueError(mode)
  value=inst.validate(z);h=topo(z,inst.n);need(h not in existing,'duplicate donor');existing.add(h)
  fresh=np.setdiff1d(edgekeys(z,inst.n),union,assume_unique=True);need(len(fresh)>0,'not genuinely novel')
  out.append((z,value,{'topology_sha256':h,'moves':trail,'new_edges_vs_all_inputs':fresh.tolist(),'new_edge_count':len(fresh)}))
 return out

def screen(job,wid):
 p=C/'unpacked'/str(job)/'o/run'/f'{wid:02d}';m,inst,ih,ip,iv,base,ref=E.admit(p/'inputs',wide=True)
 r=json.load(open(p/'run.json'));need(sha(p/'inputs/context.json')==r['source_context_sha256'],'run context');need(r['complete'] and r['branches']['2']['status']=='completed_budget','runtime');cp=p/'2/ck.txt';need(sha(cp)==r['branches']['2']['checkpoint']['sha256'],'final pin');h,pop,vals=E.read_text_checkpoint(cp,inst,100)
 jobs=[0,2] if job in (0,2) else [12,14];union,pins=union_inputs(jobs)
 groups=json.load(open(C/'RESIDUAL_SUPPORT.json'));g=groups[0 if job in (0,2) else 1];v=np.load(p/'inputs'/m['files']['vertices']['file']);support=np.flatnonzero(np.isin(v,g['common_support_vertices']));need(len(support)>0,'support absent')
 best=min(range(100),key=lambda i:(vals[i],i));worst=sorted(range(100),key=lambda i:(vals[i],i),reverse=True)[:10]
 result={'job':job,'worker':wid,'reference_local':ref,'parent_context_sha256':sha(p/'inputs/context.json'),'parent_checkpoint_sha256':sha(cp),'input_union_pins':pins,'input_edge_union_sha256':hashlib.sha256(union.astype('<i8').tobytes()).hexdigest(),'support_global_vertices':v[support].tolist(),'source_best_row':best,'replacement_rows':worst,'replaced_gaps':[int(vals[i]-ref) for i in worst],'modes':{}}
 products={}
 for mode in ('mild','strong'):
  d=donors(pop[best],inst,support,union,mode);info=[]
  for t,c,q in d:
   q['gap']=int(c-ref);q['global_delta_proof']=global_proof(t,inst,v,base,m,ref,c);info.append(q)
  result['modes'][mode]=info;products[mode]=d
 return result,products,(m,inst,h,pop,vals,base,ref)

_GLOBAL_CACHE=None
def global_proof(t,inst,v,base,m,ref,cost):
 global _GLOBAL_CACHE
 if _GLOBAL_CACHE is None:
  x=np.load(GLOBALS/'x.npy',allow_pickle=False);r=np.load(GLOBALS/'r.npy',allow_pickle=False)
  need(hashlib.sha256(np.asarray(x,dtype='<f8').tobytes()).hexdigest()=='a08055dce64382f047a314eb7cc50ec09ed85316a392b575b4783490a53926ae','coordinates identity')
  need(hashlib.sha256(np.asarray(r,dtype='<i8').tobytes()).hexdigest()=='d683d088f0c18a963230cf707c8d6af3e18710343c523f4b0346b3c97765f9a1','reference identity')
  pos=np.empty(len(r),dtype=np.int64);pos[r]=np.arange(len(r));_GLOBAL_CACHE=(x,r,pos)
 x,r,pos=_GLOBAL_CACHE;n=len(r);need(np.array_equal(x[v],inst.xyz),'global coordinates binding');need(np.array_equal(base,np.arange(inst.n)),'local reference order');need(np.all(np.diff(pos[v])>0),'global reference ordering')
 fi=np.flatnonzero((np.roll(pos[v],-1)-pos[v])%n!=1);expected=np.stack((fi,(fi+1)%inst.n),axis=1);need(np.array_equal(expected,inst.fixed),'fixed outside paths')
 def edges(t):
  a=v[t];b=np.roll(a,-1);return np.sort(np.minimum(a,b)*n+np.maximum(a,b))
 b=edges(base);e=edges(t);removed=np.setdiff1d(b,e,assume_unique=True);added=np.setdiff1d(e,b,assume_unique=True)
 def metric(keys):
  z=x[keys//n]-x[keys%n];return int(np.floor(np.sqrt(np.sum(z*z,axis=1))+.5).astype(np.int64).sum())
 delta=metric(added)-metric(removed);need(delta==cost-ref,'independent global delta cost')
 return {'reference_cost':288843498,'delta':delta,'full_cost':288843498+delta,'removed':np.c_[removed//n,removed%n].tolist(),'added':np.c_[added//n,added%n].tolist(),'delta_sha256':hashlib.sha256(removed.astype('<i8').tobytes()+b'ADDED'+added.astype('<i8').tobytes()).hexdigest(),'fixed_paths_global_binding':True}

def main():
 job=int(sys.argv[1]);wid=int(sys.argv[2]);out=Path(__file__).resolve().parent/f'screen_{job}_{wid}.json';need(not out.exists(),'fresh output required');t=time.monotonic();r,_,_=screen(job,wid);r['seconds']=time.monotonic()-t;r['status']='SCREEN_ONLY_NOT_ADMITTED';out.write_text(json.dumps(r,indent=2)+'\n');print({k:[q['gap'] for q in v] for k,v in r['modes'].items()},flush=True)
if __name__=='__main__':main()
