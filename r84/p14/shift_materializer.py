"""Exact fixed-cardinality rescoping of source tours; no search or network."""
from pathlib import Path
import hashlib,json,time,sys,tempfile
import numpy as np


def need(ok,message):
    if not ok: raise ValueError(message)

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def edge_keys(t,vertices,N):
    a=vertices[t];b=np.roll(a,-1)
    return np.sort(np.minimum(a,b)*N+np.maximum(a,b))

def delta(t,vertices,base_edges,N):
    e=edge_keys(t,vertices,N)
    return np.setdiff1d(base_edges,e,assume_unique=True),np.setdiff1d(e,base_edges,assume_unique=True)

def target_geometry(rt,x,reference,mandatory,center,size=80000):
    mandatory=np.unique(np.asarray(mandatory,dtype=np.int64))
    need(len(mandatory)<size,'support exceeds region size')
    d=np.sum((x-center)**2,axis=1);d[mandatory]=np.inf
    count=size-len(mandatory);cutoff=np.partition(d,count-1)[count-1]
    lower=np.flatnonzero(d<cutoff);tied=np.flatnonzero(d==cutoff)
    selected=np.r_[mandatory,lower,tied[:count-len(lower)]]
    need(len(selected)==size and len(np.unique(selected))==size,'selection size')
    return rt.local_geometry(x,reference,selected)[:2]

def project(rt,old_delta,new_vertices,N):
    removed,added=old_delta;n=len(new_vertices)
    # All changed endpoints are mandatory, so outside paths remain reference.
    inv=np.full(N,-1,dtype=np.int64);inv[new_vertices]=np.arange(n)
    rm=inv[np.c_[removed//N,removed%N]];ad=inv[np.c_[added//N,added%N]]
    need(np.all(rm>=0) and np.all(ad>=0),'changed endpoint omitted')
    # A 2-regular connected undirected graph has one cycle. SciPy's compiled
    # DFS removes the Python per-vertex traversal without changing edge data.
    adjacency=np.empty((n,2),dtype=np.int64)
    adjacency[:,0]=(np.arange(n)-1)%n;adjacency[:,1]=(np.arange(n)+1)%n
    for u,v in rm:
        for a,b in ((u,v),(v,u)):
            hit=np.flatnonzero(adjacency[a]==b);need(len(hit)==1,'missing removed edge');adjacency[a,hit[0]]=-1
    for u,v in ad:
        for a,b in ((u,v),(v,u)):
            free=np.flatnonzero(adjacency[a]==-1);need(len(free)>0 and b not in adjacency[a],'invalid added edge');adjacency[a,free[0]]=b
    need(np.all(adjacency>=0),'incomplete graph')
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import depth_first_order
    graph=csr_matrix((np.ones(2*n,dtype=np.int8),adjacency.ravel(),np.arange(0,2*n+1,2)),shape=(n,n))
    tour=depth_first_order(graph,0,directed=True,return_predecessors=False).astype(np.int64)
    need(len(tour)==n and len(np.unique(tour))==n,'subtour')
    successor=np.roll(tour,-1)
    need(np.all(np.any(adjacency[tour]==successor[:,None],axis=1)),'DFS did not return cycle')
    # Match the legacy apply_edges orientation (start0, next adjacency[0,1]).
    if tour[1] != adjacency[0,1]:tour=np.r_[tour[:1],tour[:0:-1]]
    need(tour[1]==adjacency[0,1],'canonical orientation')
    return tour

def choose_centers(x,core):
    pts=x[np.asarray(core,dtype=np.int64)];center=pts.mean(axis=0)
    cov=(pts-center).T@(pts-center);values,vectors=np.linalg.eigh(cov);axis=vectors[:,-1]
    major=int(np.argmax(np.abs(axis)))
    if axis[major]<0:axis=-axis
    radius=float(np.max(np.linalg.norm(pts-center,axis=1)))
    need(np.isfinite(radius) and radius>0,'residual support radius')
    return [center-.5*radius*axis,center+.5*radius*axis],{'centroid':center.tolist(),'axis':axis.tolist(),'radius':radius,'shift_radius_fraction':.5}

def prepare_job(job, collection, global_root, output, rt, core, selection_config=None):
    t0=time.monotonic();C=Path(collection);G=Path(global_root);output=Path(output)
    need(job in (0,2,12,14),'source job');need(not output.exists(),'fresh output');output.mkdir(parents=True)
    x=np.load(G/'x.npy');reference=np.load(G/'r.npy');N=len(reference)
    need(rt.digest_array(x.astype('<f8'))=='a08055dce64382f047a314eb7cc50ec09ed85316a392b575b4783490a53926ae','coordinates pin')
    need(rt.digest_array(reference.astype('<i8'))=='d683d088f0c18a963230cf707c8d6af3e18710343c523f4b0346b3c97765f9a1','reference pin')
    E=rt.engine;w0=C/'unpacked'/str(job)/'o/run/00';m,inst,h,pop,vals,base,ref,v,pos=rt.bind_global(w0/'inputs',x,reference)
    need(inst.n==80000 and m['population']==100,'dimensions');source_context=sha(w0/'inputs/context.json');be=edge_keys(base,v,N)
    workers=[];support=[]
    audits=json.load(open(C/'audits'/f'{job}.json'))
    for wid in range(4):
        w=C/'unpacked'/str(job)/'o/run'/f'{wid:02d}';run=json.load(open(w/'run.json'));branch=run['branches']['2']
        need(run['complete'] and branch['status']=='completed_budget' and branch['seconds']>=19800 and branch['returncode']==0,'runtime')
        need(sha(w/'inputs/context.json')==source_context==run['source_context_sha256'],'source binding')
        need(sha(w/'2/ck.txt')==branch['checkpoint']['sha256'],'checkpoint binding')
        header,tours,costs=E.read_text_checkpoint(w/'2/ck.txt',inst,100)
        need([int(z-ref) for z in costs]==audits['workers'][wid]['final_gaps'],'source exact gaps')
        changes=[delta(t,v,be,N) for t in tours]
        for rm,ad in changes:support.extend((rm//N,rm%N,ad//N,ad%N))
        workers.append({'header':header,'deltas':changes,'costs':costs,'checkpoint_sha256':branch['checkpoint']['sha256'],'ordered_source_sha256':rt.digest_array(np.asarray(tours,dtype='<i8'))})
    mandatory=np.unique(np.concatenate(support))
    if selection_config is None:centers,selection=choose_centers(x,core)
    else:
        centers=np.asarray(selection_config['centers'],dtype=np.float64);selection=selection_config['selection']
        need(centers.shape==(2,3) and np.isfinite(centers).all(),'pinned centers')
    need(np.all(np.isin(core,v)),'residual core outside source80k')
    summaries=[]
    for arm,center in enumerate(centers):
        armstart=time.monotonic();region=output/f'shift{arm}';region.mkdir();nv,fixed=target_geometry(rt,x,reference,mandatory,center)
        need(not np.array_equal(nv,v),'shift did not change region')
        geo=region/'geometry';geo.mkdir();rt.write_instance(geo/'instance.bin',x[nv],fixed);np.save(geo/'vertices.npy',nv.astype('<i8'))
        (geo/'base.txt').write_text('80000 0\n'+' '.join(map(str,np.arange(80000)+1))+'\n')
        newinst=E.Instance(geo/'instance.bin',m['fixm'],wide=True);newref=newinst.validate(np.arange(80000));newbase=edge_keys(np.arange(80000),nv,N)
        receipts=[]
        for wid,worker in enumerate(workers):
            dest=region/f'{wid:02d}';dest.mkdir();tours=[project(rt,d,nv,N) for d in worker['deltas']];costs=[newinst.validate(t) for t in tours]
            need([int(z-newref) for z in costs]==[int(z-ref) for z in worker['costs']],'full costs changed')
            for t,(rm,ad) in zip(tours,worker['deltas']):
                r2,a2=delta(t,nv,newbase,N);need(np.array_equal(rm,r2) and np.array_equal(ad,a2),'full edges changed')
            import shutil
            for name in ('instance.bin','vertices.npy','base.txt'):shutil.copyfile(geo/name,dest/name)
            header=list(worker['header']);header[8]=str(min(costs));E.write_checkpoint(dest/'checkpoint.txt',header,tours,costs)
            meta={k:m[k] for k in ('fixm','population','children','global_binding')};meta.update(source_run='43959844209',source_slot=f'job{job}/worker{wid}/2',ordered_population_sha256=rt.digest_array(np.asarray(tours,dtype='<i8')))
            meta['identity_evidence']={'kind':'fixed-size-region-transfer','source_context_sha256':source_context,'source_checkpoint_sha256':worker['checkpoint_sha256'],'ordered_source_population_sha256':worker['ordered_source_sha256'],'source_instance_sha256':m['files']['instance']['sha256'],'source_vertices_sha256':m['files']['vertices']['sha256'],'mandatory_support_sha256':rt.digest_array(mandatory.astype('<i8')),'all_changed_endpoints_preserved':True,'all_population_global_edge_deltas_equal':True,'all_population_cost_gaps_equal':True,'native_rng_resume':False,'source_size':80000,'target_size':80000,'selection':selection,'shift_index':arm,'target_center':center.tolist()}
            names={'instance':'instance.bin','vertices':'vertices.npy','base':'base.txt','checkpoint':'checkpoint.txt'};meta.update(schema=1,checkpoint_format='text',files={k:{'file':name,'sha256':sha(dest/name)} for k,name in names.items()});E.atomic_json(dest/'context.json',meta)
            # Read the fully written context/routes back through production admission.
            E.admit(dest,wide=True)
            receipt={'worker':wid,'routes':100,'status':'ALL100_FULL_ROUTE_DELTAS_AND_COSTS_PRESERVED','source_checkpoint_sha256':worker['checkpoint_sha256'],'context_sha256':sha(dest/'context.json'),'gaps':[int(z-newref) for z in costs]};receipts.append(receipt)
        np.save(region/'mandatory.npy',mandatory.astype('<i8'))
        newboundary=np.unique(fixed);oldboundary=np.unique(inst.fixed);coreloc=np.flatnonzero(np.isin(nv,core));oldcoreloc=np.flatnonzero(np.isin(v,core))
        from scipy.spatial import cKDTree
        nd=cKDTree(x[nv[newboundary]]).query(x[core],workers=1)[0];od=cKDTree(x[v[oldboundary]]).query(x[core],workers=1)[0]
        summary={'shift':arm,'source_job':job,'source_vertices':80000,'target_vertices':80000,'mandatory_vertices':len(mandatory),'old_vertices_retained':int(np.isin(nv,v).sum()),'new_vertices':int((~np.isin(nv,v)).sum()),'old_fixed_edges':len(inst.fixed),'new_fixed_edges':len(fixed),'geometry_instance_sha256':sha(geo/'instance.bin'),'geometry_vertices_sha256':sha(geo/'vertices.npy'),'source_context_sha256':source_context,'centering':selection,'target_center':center.tolist(),'residual_core_vertices':list(map(int,core)),'residual_core_distance_to_boundary_before':{'min':float(np.min(od)),'median':float(np.median(od))},'residual_core_distance_to_boundary_after':{'min':float(np.min(nd)),'median':float(np.median(nd))},'seconds':time.monotonic()-armstart,'workers':receipts,'search_started':False,'boundary_blocking_proven':False}
        (region/'RECEIPT.json').write_text(json.dumps(summary,indent=2)+'\n');summaries.append(summary);print(job,arm,'400 exact PASS',flush=True)
    need(summaries[0]['geometry_vertices_sha256']!=summaries[1]['geometry_vertices_sha256'],'identical shift arms')
    (output/'SUMMARY.json').write_text(json.dumps({'source_job':job,'status':'ALL800_GLOBAL_ROUTE_TRANSFERS_PASS','seconds':time.monotonic()-t0,'includes_build':False,'includes_download':False,'shifts':summaries},indent=2)+'\n')
    return summaries
