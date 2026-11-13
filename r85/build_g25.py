"""Deterministic paired80k geometry. No network, solver, checkpoint import or launch.
Inputs are already public pinned g24.bin and original coordinates gzip.
Python arbitrary-precision distance arithmetic is intentional (int64 overflows).
"""
from pathlib import Path
import argparse,gzip,hashlib,io,json,zipfile,time
import numpy as np
N=2079471
OLD_SHA='3961c3959ce870f888540897550659fdf3ed3ed8eb168adf08101683c465b0e2'
XYZ_SHA='0a613505e22d15f67372824568bce53255b088d677889bc9990299afea5735b4'
SELECTED=(0,1,2,3,6,7,10,15,17,18)
def need(v,m):
 if not v:raise ValueError(m)
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def micro(s):
 sign=-1 if s.startswith('-') else 1
 t=s.lstrip('+-').split('.');need(len(t)<=2 and t[0].isdigit(),'decimal')
 f=t[1] if len(t)==2 else '';need(len(f)<=6 and (not f or f.isdigit()),'decimal precision')
 return sign*(int(t[0])*1000000+int(f.ljust(6,'0') or '0'))
def read_coords(p):
 need(digest(p)==XYZ_SHA,'coordinate gzip SHA')
 x=np.empty((N,3),dtype='<i8');count=0
 with gzip.open(p,'rt',encoding='ascii') as f:
  for line in f:
   fields=line.split();need(count<N and len(fields)==3,'coordinates shape');x[count]=[micro(s) for s in fields];count+=1
 need(count==N,'coordinate row count');return x
def generate(x,g):
 need(x.shape==(N,3) and x.dtype==np.dtype('<i8'),'coordinate representation')
 need(set(g.files)=={'s','dr','da','i','o'},'g24 keys')
 need(np.array_equal(g['o'],np.arange(21)*80000),'g24 offsets')
 old=[g['i'][g['o'][i]:g['o'][i+1]].astype('<i4') for i in range(20)]
 for a in old:need(len(np.unique(a))==80000 and int(a.min())>=0 and int(a.max())<N,'old ids')
 centers=[tuple(sum(int(v) for v in x[a,k])//80000 for k in range(3)) for a in old]
 out=[];seen=set()
 for ri in SELECTED:
  c=centers[ri];j=min((sum((c[k]-centers[j][k])**2 for k in range(3)),j) for j in range(20) if j!=ri)[1]
  numer=tuple(2*c[k]+centers[j][k] for k in range(3));dist=np.zeros(N,dtype=object)
  for k in range(3):
   d=x[:,k].astype(object)*3-numer[k];dist+=d*d
  # Stable sort preserves global ID order for exact distance ties.
  t=np.sort(np.argsort(dist,kind='stable')[:80000]).astype('<i4');del dist,d
  key=hashlib.sha256(t.tobytes()).hexdigest();need(key not in seen,'duplicate treatment');seen.add(key)
  out.extend((old[ri],t))
 return {'s':g['s'],'dr':g['dr'].astype('<i4'),'da':g['da'].astype('<i4'),'i':np.concatenate(out).astype('<i4'),'o':np.arange(21,dtype='<i8')*80000}
def write_package(p,arrays):
 # ZIP_STORED avoids platform/zlib-dependent compression bytes.
 with zipfile.ZipFile(p,'w',compression=zipfile.ZIP_STORED) as z:
  for key,a in arrays.items():
   b=io.BytesIO();np.save(b,a,allow_pickle=False);info=zipfile.ZipInfo(key+'.npy',(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_STORED;info.external_attr=0o600<<16;z.writestr(info,b.getvalue())
def build(coords,g24,out,expected):
 start=time.monotonic();need(digest(g24)==OLD_SHA,'g24 SHA');need(not Path(out).exists(),'output already exists')
 x=read_coords(coords)
 with np.load(g24,allow_pickle=False) as g:a=generate(x,g)
 tmp=Path(str(out)+'.tmp');need(not tmp.exists(),'temporary output already exists');write_package(tmp,a)
 got=digest(tmp);need(got==expected,'generated geometry SHA mismatch');tmp.rename(out)
 return {'status':'GEOMETRY_BYTES_PASS_NOT_SEARCH_ADMISSION','sha256':got,'bytes':Path(out).stat().st_size,'seconds':time.monotonic()-start}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--coords',required=True);p.add_argument('--g24',required=True);p.add_argument('--out',required=True);p.add_argument('--expected-sha',required=True);v=p.parse_args();print(json.dumps(build(v.coords,v.g24,v.out,v.expected_sha)))
