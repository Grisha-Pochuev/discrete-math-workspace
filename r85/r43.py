"""Bounded alternate fixed-width instance generator."""
import hashlib
import numpy as np

def changed_window(ids, r, pos):
    n=len(r); width=80000; budget=4096
    p=pos[ids]; b=np.zeros(n,dtype=np.bool_); b[p]=True
    if n!=2079471 or len(ids)!=width or np.count_nonzero(b)!=width:
        raise ValueError("R-43 input scope")
    tail=np.flatnonzero(b&~np.roll(b,-1))
    head=np.flatnonzero(b&~np.roll(b,1))
    gaps=(head[np.searchsorted(head,tail,side='right')%len(head)]-tail-1)%n
    runs=(tail[np.searchsorted(tail,head)%len(tail)]-head+1)%n
    if len(head)!=len(tail) or int(gaps.sum())!=n-width or int(runs.sum())!=width:
        raise ValueError("R-43 broken run partition")
    put=[]
    left=budget
    for j in np.lexsort((tail,gaps)):
        g=int(gaps[j])
        if g>32 or left<=0:break
        if g<=left:
            put.extend((int(tail[j])+d)%n for d in range(1,g+1));left-=g
    if left:
        # Absolute distance to the nearest retained endpoint along the reference chain.
        db=np.minimum((np.arange(n)-tail[(np.searchsorted(tail,np.arange(n),side='right')-1)%len(tail)])%n,
                      (head[np.searchsorted(head,np.arange(n))%len(head)]-np.arange(n))%n)
        unused=~b
        unused[put]=False
        outside=np.flatnonzero(unused)
        put.extend(outside[np.lexsort((outside,db[outside]))[:left]].tolist())
    depth=np.zeros(n,dtype=np.int32)
    for h0,w0 in zip(head.tolist(),runs.tolist()):
        t=np.arange(w0)
        depth[(t+h0)%n]=np.minimum(t,w0-1-t)
    candidates=np.flatnonzero(b & (depth>=4))
    order=np.lexsort((candidates,-depth[candidates]))
    drop=candidates[order[:budget]]
    if len(drop)!=budget or len(set(put))!=budget or b[put].any():
        raise ValueError("R-43 insufficient supported change")
    y=b.copy();y[drop]=False;y[put]=True
    f=int(np.count_nonzero(y&~np.roll(y,-1)))
    newly_internal=int(np.count_nonzero((y&np.roll(y,-1))&~(b&np.roll(b,-1))))
    if np.count_nonzero(y)!=width or f>8000 or f<=0 or newly_internal<budget:
        raise ValueError("R-43 structural check")
    sel=np.sort(r[np.flatnonzero(y)]).astype(np.int64)
    h=hashlib.sha256(sel.astype('<i8').tobytes()).hexdigest()
    return sel,dict(width=width,changed=budget,old_fixed=len(head),new_fixed=f,new_internal=newly_internal,membership_sha256=h)

def starting_pool(vertices, near, fixed, length, nseed, size=100):
    """Deterministic bounded routes made from disjoint mutable two-edge exchanges."""
    n=len(vertices)
    if (n,near.shape,size)!=(80000,(80000,50),100):
        raise ValueError("R-43 start scope")
    I=[];J=[];D=[]; ref=length(vertices,np.roll(vertices,-1))
    for lo in range(0,n,4096):
        hi=min(n,lo+4096)
        a=np.broadcast_to(np.arange(lo,hi)[:,None],(hi-lo,50)); b=near[lo:hi]
        mask=(b>a+1)&(b<n-1)&(~fixed[a])&(~fixed[b])
        u,v=a[mask],b[mask]
        d=length(vertices[u],vertices[v])+length(vertices[u+1],vertices[v+1])-ref[u]-ref[v]
        mask=(d>=-10)&(d<=45)
        I.extend(u[mask].tolist()); J.extend(v[mask].tolist()); D.extend(d[mask].tolist())
    if len(I)<size*4:
        raise ValueError("R-43 insufficient feasible starts")
    rng=np.random.default_rng(nseed)
    rows=[np.arange(n,dtype=np.int32)]; seen=set(); gaps=[0]
    for attempt in range(4000):
        target=1+attempt%4; selected=[]; ds=0
        for k in rng.integers(0,len(I),size=16):
            i,j=I[k],J[k]
            if any(not (j<q or i>r) for q,r in selected):continue
            selected.append((i,j));ds+=D[k]
            if len(selected)>=target:break
        key=tuple(sorted(selected))
        if len(selected)!=target or key in seen:continue
        seen.add(key)
        t=np.arange(n,dtype=np.int32)
        for i,j in key:t[i+1:j+1]=t[i+1:j+1][::-1]
        rows.append(t);gaps.append(ds)
        if len(rows)==size:break
    if len(rows)!=size:
        raise ValueError("R-43 too few independent feasible starts")
    return rows,gaps
