"""Local preparation prototype. No network, claims, solver, or dispatch."""
import argparse, ctypes as C, gzip, hashlib, json, resource, sys, time, zipfile
from pathlib import Path
import numpy as np

def need(x, msg):
    if not x: raise ValueError(msg)
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser()
    for x in ('manifest','parent','geometry','coordinates','reference','tools','exact','output'): p.add_argument('--'+x,type=Path,required=True)
    p.add_argument('--index',type=int,required=True);a=p.parse_args();t=time.monotonic()
    m=json.loads(a.manifest.read_text());need(0<=a.index<len(m['parents']),'index');r=m['parents'][a.index]
    for f,h in ((a.parent,r['zip_sha256']),(a.geometry,m['geometry_sha256']),(a.coordinates,m['coordinates_sha256']),(a.reference,m['reference_sha256'])):need(sha(f)==h,'input digest')
    need(not a.output.exists(),'output exists: no replay');a.output.mkdir()
    parent=a.output/'parent';parent.mkdir()
    with zipfile.ZipFile(a.parent) as z:
        items=z.infolist();need(len(items)<=128 and sum(x.file_size for x in items)<=512*1024**2,'ZIP size')
        need(len({x.filename for x in items})==len(items),'duplicate entry')
        for x in items:
            need('/' not in x.filename and '\\' not in x.filename and x.filename not in ('','.','..') and not x.is_dir(),'flat regular archive')
            need((x.external_attr>>16)&0o170000 in (0,0o100000),'regular entry')
        need(z.testzip() is None,'CRC');z.extractall(parent)
    s=json.loads((parent/'s.json').read_text());need(s['runtime_identity']=={'GITHUB_RUN_ID':str(m['parent_run']),'GITHUB_RUN_ATTEMPT':str(m['parent_attempt']),'GITHUB_SHA':m['parent_head']},'run identity')
    sys.path.insert(0,str(a.tools.resolve()));import region_tools as rt
    bundle=a.output/'bundle';meta=rt.import_parent(parent,a.geometry,a.coordinates,a.reference,r['slot'],r['island'],r['parent_root'],bundle)
    need(meta['ordered_population_sha256']==r['ordered_population_sha256'],'ordered population')
    need(sha(bundle/'context.json')==r['context_sha256'],'context byte identity')
    for name,h in r['expected_file_hashes'].items():need(sha(bundle/name)==h,'generated data identity '+name)
    v=np.load(bundle/'vertices.npy',allow_pickle=False);n=len(v)
    # Parse decimal coordinates directly, independently of floating-point importer.
    micro=np.empty((2079471,3),np.int64)
    def parse(s):
        sign=-1 if s.startswith('-') else 1;b=s.lstrip('+-').split('.');f=b[1] if len(b)==2 else '';need(len(b)<=2 and len(f)<=6,'decimal');return sign*(int(b[0])*1000000+int(f.ljust(6,'0') or '0'))
    count=0
    with gzip.open(a.coordinates,'rt') as f:
        for count,line in enumerate(f,1):
            need(count<=len(micro),'coordinate count');micro[count-1]=[parse(x) for x in line.split()]
    need(count==len(micro),'coordinate count');xyz=np.ascontiguousarray(micro[v]);del micro
    lib=C.CDLL(str(a.exact.resolve()));lib.fullcost.argtypes=[C.c_int,C.c_void_p,C.c_void_p];lib.fullcost.restype=C.c_int64
    base=np.arange(n,dtype=np.int32);ref=lib.fullcost(n,base.ctypes.data,xyz.ctypes.data);gaps=[]
    import math
    with (bundle/'instance.bin').open('rb') as f:
        nn,nf,k=np.fromfile(f,'<i4',3);need(nn==n,'instance count');f.seek(n*24,1);fixed=np.fromfile(f,'<i4',2*nf).reshape(nf,2)
    fkeys=np.sort(np.minimum(fixed[:,0],fixed[:,1]).astype(np.int64)*n+np.maximum(fixed[:,0],fixed[:,1]))
    offset=0
    for u,vv in fixed:
        q=sum((int(xyz[u,k])-int(xyz[vv,k]))**2 for k in range(3));d=math.isqrt(q)//1000000;d+=4*q>=1000000000000*(2*d+1)**2;offset+=d+200000

    with (bundle/'checkpoint.txt').open() as f:
        header=f.readline()
        for row,expected in enumerate(r['ordered_edge_hashes']):
            size,price=map(int,f.readline().split());tour=np.asarray([int(x)-1 for x in f.readline().split()],np.int32)
            need(size==n and np.array_equal(np.sort(tour),base),'permutation')
            edges=np.sort(np.minimum(tour,np.roll(tour,-1)).astype(np.int64)*n+np.maximum(tour,np.roll(tour,-1)))
            need(hashlib.sha256(edges.tobytes()).hexdigest()==expected,'independent ordered edges')
            need(np.isin(fkeys,edges).all(),'independent fixed edges');cost=lib.fullcost(n,tour.ctypes.data,xyz.ctypes.data);need(cost-offset==price,'integer penalized price');gaps.append(cost-ref)
        need(len(gaps)==100 and not f.read().strip(),'population count')
    need(sum(gaps)/100==r['initial_mean_gap'],'mean gap')
    receipt={'status':'LOCAL_MATERIALIZATION_AND_100_EXACT_PASS_NOT_RUNTIME_ADMISSION','slot':r['slot'],'island':r['island'],'routes':100,'seconds':time.monotonic()-t,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'context_sha256':sha(bundle/'context.json'),'expected_context_equal':sha(bundle/'context.json')==r['context_sha256'],'search_started':False}
    (a.output/'RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
if __name__=='__main__':main()
