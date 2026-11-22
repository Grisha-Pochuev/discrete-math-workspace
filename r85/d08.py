"""Checked non-identity initial population members, in unchanged instance order."""
from pathlib import Path
import hashlib
import json
import numpy as np

H = '562105642b4cf2c50cfb4c0ff9086432d8a47d99921a4663cf7a2455662c531e'
L = {122: 1, 124: 1, 135: 1}

def load(path=None):
    blob = (Path(__file__).with_suffix('.json') if path is None else Path(path)).read_bytes()
    if hashlib.sha256(blob).hexdigest() != H:
        raise ValueError('d07 digest')
    j = {int(k): v for k,v in json.loads(blob).items()}
    if {k: len(v) for k,v in j.items()} != L:
        raise ValueError('d07 count')
    return j

def decode(row, N, Lc, fx, cost, ref):
    n = len(Lc)
    look = {int(v):i for i,v in enumerate(Lc)}
    fixed = {tuple(sorted((int(i),(int(i)+1)%n))) for i in np.flatnonzero(fx)}
    adj = [{(i-1)%n,(i+1)%n} for i in range(n)]
    for tag in ('r','a'):
        keys = row[tag]
        if any(type(v)!=int for v in keys) or keys!=sorted(set(keys)):
            raise ValueError('d07 array')
        for key in keys:
            u,v = divmod(key,N)
            if not 0 <= u < v < N or u not in look or v not in look:
                raise ValueError('d07 domain')
            i,j = look[u],look[v]
            if tag=='r':
                if j not in adj[i] or tuple(sorted((i,j))) in fixed:
                    raise ValueError('d07 invariant removal')
                adj[i].remove(j); adj[j].remove(i)
            else:
                if j in adj[i]:
                    raise ValueError('d07 repeated edge')
                adj[i].add(j); adj[j].add(i)
    if len(row['r']) != len(row['a']) or not row['r'] or any(len(a)!=2 for a in adj):
        raise ValueError('d07 degree')
    nxt = [sorted(a) for a in adj]
    seq = np.empty(n,dtype=np.int64); prev=-1; curr=0
    for i in range(n):
        seq[i]=curr; a,b=nxt[curr]; prev,curr=curr,(b if a==prev else a)
    if curr!=0 or not np.all(np.bincount(seq,minlength=n)==1):
        raise ValueError('d07 disconnected')
    if cost(seq) != ref:
        raise ValueError('d07 inconsistent cost')
    return seq

def prepare(pop, rows, cost, topology, anchor, ref):
    """Replace worst eligible slots, preserving existing donors/anchor and any better seq."""
    hashes = [topology(t) for t in pop]
    d = [(topology(t),label,t) for label,t in rows]
    if len({h for h,_,_ in d}) != len(d) or any(h==anchor for h,_,_ in d):
        raise ValueError('d07 distinctness')
    keep = {h for h,_,_ in d}|{anchor}
    vals = [cost(t) for t in pop]
    if any(v is None for v in vals):
        raise ValueError('d07 invalid parent')
    available = sorted((i for i,(h,v) in enumerate(zip(hashes,vals)) if h not in keep and v >= ref),
                       key=lambda i:(vals[i],i),reverse=True)
    inserted=[]
    for h,label,t in d:
        if h in hashes:
            continue
        if not available:
            raise ValueError('d07 no admissible replacement slot')
        i=available.pop(0); pop[i]=t.copy(); hashes[i]=h; inserted.append(label)
    if not all(h in hashes for h,_,_ in d):
        raise ValueError('d07 lost member')
    return inserted
