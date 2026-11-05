from __future__ import annotations
import hashlib, itertools, json
from array import array
from run000_core import edge, fixed_remainder, matching_mask, perfect_matchings

def r_preserving_vertex_maps(n):
    pairs=n//2
    for pair_perm in itertools.permutations(range(pairs)):
        for flips in itertools.product((0,1),repeat=pairs):
            mapping=[0]*n
            for old in range(pairs):
                new=pair_perm[old]
                for side in (0,1): mapping[2*old+side]=2*new+(side^flips[old])
            yield tuple(mapping)

def n10_orbit_representatives():
    n=10; remainder=fixed_remainder(n); redges=set(remainder)
    all_m=perfect_matchings(tuple(range(n)))
    allowed=[m for m in all_m if set(m).isdisjoint(redges)]; A=len(allowed); index={m:i for i,m in enumerate(allowed)}
    complete_edges=tuple(itertools.combinations(range(n),2)); eid={e:i for i,e in enumerate(complete_edges)}
    masks=[matching_mask(m,eid) for m in allowed]
    disjoint=[]; dsets=[]
    for i in range(A):
        row=[j for j in range(A) if not (masks[i]&masks[j])]; disjoint.append(row); dsets.append(set(row))
    space=A**3; bits=bytearray((space+7)//8); valid=0
    for i in range(A):
        si=dsets[i]
        for j in disjoint[i]:
            for k in si.intersection(dsets[j]):
                code=(i*A+j)*A+k; bits[code>>3]|=1<<(code&7); valid+=1
    transforms=[]
    for mapping in r_preserving_vertex_maps(n):
        arr=array('H')
        for matching in allowed:
            image=tuple(sorted(edge(mapping[u],mapping[v]) for u,v in matching)); arr.append(index[image])
        transforms.append(arr)
    perms=tuple(itertools.permutations(range(3)))
    def is_set(code): return bool(bits[code>>3]&(1<<(code&7)))
    def clear(code): bits[code>>3]&=~(1<<(code&7))
    def next_set(start):
        bi=start>>3
        if bi>=len(bits): return None
        val=bits[bi]&((0xFF<<(start&7))&0xFF)
        while True:
            if val:
                low=val&-val; return (bi<<3)+(low.bit_length()-1)
            bi+=1
            if bi>=len(bits): return None
            val=bits[bi]
    reps=[]; cursor=cleared=0
    while True:
        code=next_set(cursor)
        if code is None or code>=space: break
        i=code//(A*A); rem=code%(A*A); j=rem//A; k=rem%A; reps.append((i,j,k))
        for arr in transforms:
            vals=(arr[i],arr[j],arr[k])
            for p in perms:
                c=(vals[p[0]]*A+vals[p[1]])*A+vals[p[2]]
                if is_set(c): clear(c); cleared+=1
        cursor=code+1
    assert cleared==valid,(cleared,valid)
    rep_matchings=[tuple(allowed[x] for x in rep) for rep in reps]
    digest=hashlib.sha256(json.dumps(rep_matchings,separators=(',',':')).encode()).hexdigest()
    return rep_matchings,digest,{'allowed_matchings':A,'labelled_factor_triples':valid}
