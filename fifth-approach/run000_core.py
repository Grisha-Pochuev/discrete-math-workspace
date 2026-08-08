from __future__ import annotations

import gzip
import hashlib
import itertools
import json
import os
import random
import signal
import time
from collections import Counter
from functools import lru_cache
from pathlib import Path

STOP = False

def _stop(_signum, _frame):
    global STOP
    STOP = True

signal.signal(signal.SIGTERM, _stop)
signal.signal(signal.SIGINT, _stop)

def edge(u: int, v: int):
    return (u, v) if u < v else (v, u)

@lru_cache(maxsize=None)
def perfect_matchings(vertices: tuple[int, ...]):
    if not vertices:
        return ((),)
    u = vertices[0]
    out = []
    for i in range(1, len(vertices)):
        v = vertices[i]
        rest = vertices[1:i] + vertices[i+1:]
        for tail in perfect_matchings(rest):
            out.append(tuple(sorted(((u, v),) + tail)))
    return tuple(out)

def fixed_remainder(n: int):
    return tuple((2*i, 2*i+1) for i in range(n//2))

def connected(n: int, matchings):
    adj = [[] for _ in range(n)]
    for matching in matchings:
        for u, v in matching:
            adj[u].append(v); adj[v].append(u)
    seen, stack = {0}, [0]
    while stack:
        u = stack.pop()
        for v in adj[u]:
            if v not in seen:
                seen.add(v); stack.append(v)
    return len(seen) == n

def matching_mask(matching, edge_id):
    mask = 0
    for e in matching:
        mask |= 1 << edge_id[edge(*e)]
    return mask

def enumerate_graph_matchings(n, edge_set, edge_id):
    adj = [[] for _ in range(n)]
    for u, v in edge_set:
        adj[u].append(v); adj[v].append(u)
    out = []
    def rec(remaining, chosen):
        if remaining == 0:
            out.append(chosen); return
        low = remaining & -remaining
        u = low.bit_length() - 1
        rem = remaining & ~low
        for v in adj[u]:
            vb = 1 << v
            if rem & vb:
                rec(rem & ~vb, chosen | (1 << edge_id[edge(u, v)]))
    rec((1 << n)-1, 0)
    return tuple(out)

def build_system(n, factors, remainder=None):
    remainder = fixed_remainder(n) if remainder is None else remainder
    factors = tuple(tuple(sorted(edge(*e) for e in m)) for m in factors)
    remainder = tuple(sorted(edge(*e) for e in remainder))
    edges = set(remainder)
    for m in factors: edges.update(m)
    edge_list = tuple(sorted(edges)); edge_id = {e:i for i,e in enumerate(edge_list)}
    factor_of_edge = {e:q for q,m in enumerate(factors) for e in m}
    full = enumerate_graph_matchings(n, edges, edge_id)
    h_edges = set().union(*[set(m) for m in factors])
    h_matchings = enumerate_graph_matchings(n, h_edges, edge_id)
    h_meta = []
    for mask in h_matchings:
        colours = {factor_of_edge[e] for i,e in enumerate(edge_list) if mask & (1<<i) and e in factor_of_edge}
        h_meta.append((mask, len(colours) >= 2))
    return dict(n=n, factors=factors, remainder=remainder, edge_list=edge_list,
                edge_id=edge_id, factor_of_edge=factor_of_edge,
                full_matchings=full, h_meta=tuple(h_meta))

def trap_halves(system, duplicated):
    n = system['n']; remainder = system['remainder']; factor_of_edge = system['factor_of_edge']
    k_edges = set(remainder)
    for q, matching in enumerate(system['factors']):
        for u,v in matching:
            if duplicated[u] == q and duplicated[v] == q:
                k_edges.add((u,v))
    adj = [[] for _ in range(n)]
    for u,v in k_edges: adj[u].append(v); adj[v].append(u)
    remset = set(remainder); seen = set(); traps = []
    for start in range(n):
        if start in seen: continue
        stack=[start]; comp=set()
        while stack:
            u=stack.pop()
            if u in comp: continue
            comp.add(u); stack.extend(v for v in adj[u] if v not in comp)
        seen.update(comp)
        if any(len(adj[u]) != 2 for u in comp): continue
        comp_edges = {edge(u,v) for u in comp for v in adj[u] if u<v}
        medges = comp_edges - remset
        if len({factor_of_edge[e] for e in medges}) < 2: continue
        mmask=rhalf=0
        for e in comp_edges:
            bit = 1 << system['edge_id'][e]
            if e in remset: rhalf |= bit
            else: mmask |= bit
        traps.append((mmask,rhalf))
    return tuple(sorted(traps))

def induced_colouring(system, mask, duplicated):
    colours=[-1]*system['n']; remset=set(system['remainder'])
    for i,e in enumerate(system['edge_list']):
        if not mask & (1<<i): continue
        u,v=e
        if e in remset:
            colours[u]=duplicated[u]; colours[v]=duplicated[v]
        else:
            q=system['factor_of_edge'][e]; colours[u]=q; colours[v]=q
    return tuple(colours)

def evaluate_assignment(system, duplicated):
    traps = trap_halves(system, duplicated)
    if not traps: return None
    h_safe = sum(1 for mask,mixed in system['h_meta'] if mixed and all((mask&m)!=m for m,_ in traps))
    full_safe=0; first=None
    for mask in system['full_matchings']:
        colouring=induced_colouring(system, mask, duplicated)
        if len(set(colouring)) < 2: continue
        if all((mask&m)!=m and (mask&r)!=r for m,r in traps):
            full_safe += 1
            if first is None: first=(mask,colouring)
    return len(traps), h_safe, full_safe, first

def assignment_record(system, duplicated, result):
    traps,h_safe,full_safe,first=result
    rec={'duplicated':list(duplicated),'trap_count':traps,'h_safe':h_safe,'full_safe':full_safe}
    if first is not None:
        mask,colouring=first; rec['safe_colouring']=list(colouring)
        rec['safe_matching']=[list(e) for i,e in enumerate(system['edge_list']) if mask&(1<<i)]
    return rec

def scan_all_assignments(system, deadline=None, checkpoint_every=4096):
    total=3**system['n']; checked=trap_cases=h_fail=full_fail=0
    min_h=min_full=None; trap_hist=Counter(); safe_hist=Counter(); hard=[]
    for duplicated in itertools.product(range(3), repeat=system['n']):
        checked += 1
        if checked % checkpoint_every == 0 and (STOP or (deadline is not None and time.monotonic() >= deadline)):
            return dict(complete=False, assignments_checked=checked, assignments_total=total,
                        trap_cases=trap_cases, h_only_failures=h_fail, corrected_failures=full_fail,
                        minimum_h_safe=min_h, minimum_full_safe=min_full,
                        trap_histogram=dict(trap_hist), full_safe_histogram=dict(safe_hist), hard_cases=hard)
        ev=evaluate_assignment(system, duplicated)
        if ev is None: continue
        tc,hs,fs,_=ev; trap_cases += 1; trap_hist[tc] += 1; safe_hist[fs] += 1
        min_h=hs if min_h is None else min(min_h,hs); min_full=fs if min_full is None else min(min_full,fs)
        if hs==0: h_fail += 1
        if fs==0: full_fail += 1
        hard.append(assignment_record(system, duplicated, ev))
        hard.sort(key=lambda x:(x['full_safe'],x['h_safe'],-x['trap_count'])); del hard[6:]
    return dict(complete=True, assignments_checked=checked, assignments_total=total,
                trap_cases=trap_cases, h_only_failures=h_fail, corrected_failures=full_fail,
                minimum_h_safe=min_h, minimum_full_safe=min_full,
                trap_histogram=dict(trap_hist), full_safe_histogram=dict(safe_hist), hard_cases=hard)

def random_disjoint_factor_system(n, rng):
    remainder=fixed_remainder(n); rset=set(remainder)
    for _ in range(10000):
        factors=[]; used=set(rset); ok=True
        for _q in range(3):
            found=None
            for _ in range(1000):
                vertices=list(range(n)); rng.shuffle(vertices)
                m=tuple(sorted(edge(vertices[i],vertices[i+1]) for i in range(0,n,2)))
                if set(m).isdisjoint(used): found=m; break
            if found is None: ok=False; break
            factors.append(found); used.update(found)
        if ok and connected(n, tuple(factors)+(remainder,)):
            return tuple(factors), remainder
    raise RuntimeError('failed to sample connected factor system')

def system_signature(factors, remainder):
    raw=json.dumps({'factors':factors,'remainder':remainder},separators=(',',':'),sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()

def merge_scan(dst, scan):
    for key in ('assignments_checked','trap_cases','h_only_failures','corrected_failures'):
        dst[key]=dst.get(key,0)+int(scan.get(key,0) or 0)
    dst['systems_completed' if scan.get('complete') else 'systems_partial']=dst.get('systems_completed' if scan.get('complete') else 'systems_partial',0)+1
    for key in ('minimum_h_safe','minimum_full_safe'):
        val=scan.get(key)
        if val is not None: dst[key]=val if dst.get(key) is None else min(dst[key],val)
    dst.setdefault('hard_cases',[]).extend(scan.get('hard_cases',[]))
    dst['hard_cases'].sort(key=lambda x:(x['full_safe'],x['h_safe'],-x['trap_count'])); del dst['hard_cases'][10:]

def atomic_write_gz(path, data):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+'.tmp')
    with gzip.open(tmp,'wt',encoding='utf-8',compresslevel=6) as f:
        json.dump(data,f,indent=2,sort_keys=True); f.write('\n')
    os.replace(tmp,path)

def adversarial_search(system, rng, deadline, trials=30000):
    n=system['n']; best=None; checked=0; current=[rng.randrange(3) for _ in range(n)]; current_score=None
    for step in range(trials):
        if STOP or (step%1024==0 and time.monotonic()>=deadline): break
        if step==0 or step%400==0: candidate=[rng.randrange(3) for _ in range(n)]
        else:
            candidate=current[:]; pos=rng.randrange(n); candidate[pos]=(candidate[pos]+rng.randrange(1,3))%3
        ev=evaluate_assignment(system,tuple(candidate)); checked+=1
        if ev is None: score=(10**9,0,0)
        else:
            tc,hs,fs,_=ev; score=(fs,hs,-tc); rec=assignment_record(system,tuple(candidate),ev)
            if best is None or score<best[0]: best=(score,rec)
        if current_score is None or score<=current_score or rng.random()<0.01:
            current=candidate; current_score=score
        if best is not None and best[0][0]==0: break
    return checked, None if best is None else best[1]
