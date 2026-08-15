#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import math
import os
import random
import re
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from ortools.sat.python import cp_model
from sympy import factorint as sympy_factorint

SOURCE_URL = 'https://www.d.umn.edu/~jgreene/baillie/Baillie-PSW.html'
M_BIG = int(
    '391503310121204881113221826377421073230588550480847994760111'
    '437264285933394797561252633748976272034752759144054959758356'
    '281631740751422332870766577461271728486411722501243608126322'
    '081539854254895422161780480832565829680409393157195431459784'
    '481602760641763660786715059347404742'
)
N_BIG = int(
    '234140225752418688005464457713566506358755719892017711133836'
    '422331572174538952682649975569313518021383999970255887289214'
    '770286598356807954528507483688540755157670239035842269509644'
    '277978341717565068329104640284794943619967653440781565902586'
    '799586600590853417916276540721230114816'
)
OUT = Path(os.environ.get('BPSW_OUT', 'enhanced_bpsw/out'))


def sieve_primes(n: int) -> List[int]:
    a = bytearray(b'\x01') * (n + 1)
    a[:2] = b'\x00\x00'
    for p in range(2, int(n**0.5) + 1):
        if a[p]:
            a[p*p:n+1:p] = b'\x00' * (((n - p*p)//p) + 1)
    return [i for i, v in enumerate(a) if v]

SMALL_PRIMES = sieve_primes(5000)


def factor_over(n: int, base: Sequence[int]) -> Dict[int, int]:
    out: Dict[int, int] = {}
    x = n
    for p in base:
        if p*p > x and x > 1:
            break
        if x % p == 0:
            e = 0
            while x % p == 0:
                x //= p
                e += 1
            out[p] = e
    if x > 1:
        if x <= 10_000 and is_prime64(x):
            out[x] = out.get(x, 0) + 1
            x = 1
    if x != 1:
        raise ValueError(f'Unfactored cofactor {x} in {n}')
    return out


def is_prime64(n: int) -> bool:
    if n < 2:
        return False
    small = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)
    for p in small:
        if n % p == 0:
            return n == p
    d = n - 1
    s = 0
    while d % 2 == 0:
        s += 1
        d //= 2
    for a in (2, 325, 9375, 28178, 450775, 9780504, 1795265022):
        if a % n == 0:
            continue
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = x*x % n
            if x == n - 1:
                break
        else:
            return False
    return True


def v2(n: int) -> int:
    if n == 0:
        raise ValueError('v2(0)')
    return (n & -n).bit_length() - 1


def legendre(a: int, p: int) -> int:
    r = pow(a % p, (p - 1)//2, p)
    if r == 1:
        return 1
    if r == p - 1:
        return -1
    return 0


def jacobi(a: int, n: int) -> int:
    if n <= 0 or n % 2 == 0:
        raise ValueError('Jacobi denominator must be positive odd')
    a %= n
    result = 1
    while a:
        while a % 2 == 0:
            a //= 2
            if n % 8 in (3, 5):
                result = -result
        a, n = n, a
        if a % 4 == n % 4 == 3:
            result = -result
        a %= n
    return result if n == 1 else 0


def multiplicative_order(a: int, p: int, factors_p_minus_1: Dict[int, int]) -> int:
    order = p - 1
    for q in factors_p_minus_1:
        while order % q == 0 and pow(a, order // q, p) == 1:
            order //= q
    return order


def fib_pair_mod(n: int, mod: int) -> Tuple[int, int]:
    if n == 0:
        return 0, 1
    a, b = fib_pair_mod(n >> 1, mod)
    c = a * ((2*b - a) % mod) % mod
    d = (a*a + b*b) % mod
    if n & 1:
        return d, (c + d) % mod
    return c, d


def fib_mod(n: int, mod: int) -> int:
    return fib_pair_mod(n, mod)[0]


def fibonacci_rank_from_multiple(p: int, multiple: int, factors: Dict[int, int]) -> int:
    rank = multiple
    if fib_mod(rank, p) != 0:
        raise ValueError(f'F_multiple nonzero for p={p}, multiple={multiple}')
    for q in factors:
        while rank % q == 0 and fib_mod(rank // q, p) == 0:
            rank //= q
    return rank


def merge_lcm_factorization(values: Iterable[int], allowed: Sequence[int]) -> Dict[int, int]:
    out: Dict[int, int] = {}
    for x in values:
        f = factor_over(x, allowed)
        for p, e in f.items():
            if e > out.get(p, 0):
                out[p] = e
    return out


def from_factorization(f: Dict[int, int]) -> int:
    x = 1
    for p, e in f.items():
        x *= p**e
    return x


def prime_factors_small(n: int) -> List[int]:
    return list(factor_over(n, SMALL_PRIMES).keys())


def primitive_root_prime_power(q: int, e: int) -> Tuple[int, int, int]:
    mod = q**e
    if q == 2:
        if e == 1:
            return 1, mod, 1
        if e == 2:
            return 3, mod, 2
        raise ValueError('Unit group modulo 2^e is non-cyclic for e>=3')
    phi = q**(e - 1) * (q - 1)
    pf = prime_factors_small(phi)
    for g in range(2, mod):
        if math.gcd(g, mod) != 1:
            continue
        if all(pow(g, phi // r, mod) != 1 for r in pf):
            return g, mod, phi
    raise RuntimeError(f'No primitive root modulo {mod}')


def dlog_table(g: int, mod: int, order: int) -> Dict[int, int]:
    table: Dict[int, int] = {}
    x = 1
    for k in range(order):
        if x in table:
            raise RuntimeError(f'Generator repeats early modulo {mod}')
        table[x] = k
        x = x*g % mod
    if x != 1 or len(table) != order:
        raise RuntimeError(f'Bad dlog table modulo {mod}')
    return table


def fetch_pools() -> Tuple[List[int], List[int]]:
    req = urllib.request.Request(SOURCE_URL, headers={'User-Agent': 'Mozilla/5.0'})
    raw = urllib.request.urlopen(req, timeout=90).read().decode('latin-1')
    text = html.unescape(raw)
    pools: List[List[int]] = []
    for block in re.findall(r'P\s*=\s*\{(.*?)\}', text, flags=re.S | re.I):
        nums = [int(x) for x in re.findall(r'\d+', block)]
        if len(nums) >= 100:
            pools.append(nums)
    pools.sort(key=len)
    if len(pools) < 2 or len(pools[-2]) != 1248 or len(pools[-1]) != 4838:
        raise RuntimeError(f'Unexpected pool sizes: {[len(x) for x in pools]}')
    return pools[-2], pools[-1]


def mat_mul(A: Tuple[int, int, int, int], B: Tuple[int, int, int, int], mod: int) -> Tuple[int, int, int, int]:
    a,b,c,d = A
    e,f,g,h = B
    return ((a*e+b*g)%mod, (a*f+b*h)%mod,
            (c*e+d*g)%mod, (c*f+d*h)%mod)


def mat_pow_companion(P: int, Q: int, k: int, mod: int) -> Tuple[int, int, int, int]:
    R = (1,0,0,1)
    A = (P % mod, (-Q) % mod, 1, 0)
    while k:
        if k & 1:
            R = mat_mul(R, A, mod)
        A = mat_mul(A, A, mod)
        k >>= 1
    return R


def lucas_uv(P: int, Q: int, k: int, mod: int) -> Tuple[int, int]:
    if k == 0:
        return 0, 2 % mod
    A = mat_pow_companion(P, Q, k, mod)
    U = A[2] % mod
    U_next = A[0] % mod
    V = (2*U_next - P*U) % mod
    return U, V


def strong_prp(n: int, a: int) -> Tuple[bool, str]:
    d = n - 1
    s = v2(d)
    d >>= s
    x = pow(a, d, n)
    if x == 1:
        return True, 'U'
    for r in range(s):
        if x == n - 1:
            return True, f'V{r}'
        x = x*x % n
    return False, 'fail'


def strong_lucas(n: int, P: int, Q: int, D: int) -> Tuple[bool, str]:
    eps = jacobi(D, n)
    if eps != -1:
        return False, f'jacobi={eps}'
    t = n + 1
    s = v2(t)
    d = t >> s
    U, V = lucas_uv(P, Q, d, n)
    if U == 0:
        return True, 'U_d'
    qpow = pow(Q, d, n)
    curV = V
    for r in range(s):
        if curV == 0:
            return True, f'V_{r}'
        curV = (curV*curV - 2*qpow) % n
        qpow = qpow*qpow % n
    return False, 'fail'


def method_a_star(n: int) -> Tuple[int, int, int]:
    k = 0
    while True:
        abs_d = 5 + 2*k
        D = abs_d if k % 2 == 0 else -abs_d
        j = jacobi(D, n)
        if j == -1:
            P = 1
            Q = (1 - D)//4
            if Q == -1:
                P = Q = 5
            return D, P, Q
        if j == 0:
            raise ValueError(f'Method A* encountered gcd at D={D}')
        k += 1
        if k > 1000:
            raise RuntimeError('Method A* did not terminate')


def build_rows(primes: Sequence[int], fac_minus: Dict[int,int], fac_plus: Dict[int,int]):
    rows = []
    for side, fac in [('minus', fac_minus), ('plus', fac_plus)]:
        for q, e in sorted(fac.items()):
            if q == 2 and e == 1:
                continue
            g, mod, group_order = primitive_root_prime_power(q, e)
            tab = dlog_table(g, mod, group_order)
            coeff = []
            for p in primes:
                r = p % mod
                if r not in tab:
                    raise RuntimeError(f'p={p} is not a unit/generated residue modulo {mod}')
                coeff.append(tab[r])
            target = 0 if side == 'minus' else (group_order // 2)
            if side == 'plus' and pow(g, target, mod) != (mod - 1) % mod:
                raise RuntimeError(f'Bad -1 logarithm modulo {mod}')
            rows.append({'side':side,'prime_power':mod,'generator':g,
                         'modulus':group_order,'target':target,'coeff':coeff})
    return rows


def solve_subset(primes: Sequence[int], rows, time_limit: float, seed: int):
    model = cp_model.CpModel()
    xs = [model.NewBoolVar(f'x_{i}') for i in range(len(primes))]
    model.Add(sum(xs) >= 3)
    for j,row in enumerate(rows):
        coeff = row['coeff']
        m = int(row['modulus'])
        b = int(row['target'])
        max_sum = sum(coeff)
        kmin = math.ceil((-b)/m)
        kmax = (max_sum-b)//m
        if kmax < kmin:
            raise RuntimeError(f'Empty k range in row {j}')
        kv = model.NewIntVar(kmin,kmax,f'k_{j}')
        model.Add(sum(c*x for c,x in zip(coeff,xs) if c) == b + m*kv)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = int(os.environ.get('BPSW_WORKERS','4'))
    solver.parameters.random_seed = seed
    solver.parameters.randomize_search = True
    solver.parameters.cp_model_presolve = True
    solver.parameters.log_search_progress = True
    solver.parameters.log_to_stdout = True
    status = solver.Solve(model)
    chosen = [i for i,x in enumerate(xs)
              if status in (cp_model.OPTIMAL,cp_model.FEASIBLE) and solver.Value(x)]
    return status,chosen,solver.ResponseStats()


def main() -> int:
    OUT.mkdir(parents=True,exist_ok=True)
    small,pool = fetch_pools()
    (OUT/'chen_small_1248.txt').write_text('\n'.join(map(str,small))+'\n')
    (OUT/'chen_large_4838.txt').write_text('\n'.join(map(str,pool))+'\n')

    base = sieve_primes(1300)
    fm = factor_over(M_BIG,base)
    fn = factor_over(N_BIG,base)
    assert math.gcd(M_BIG,N_BIG)==2

    records=[]
    bad=[]
    for p in pool:
        if not is_prime64(p):
            bad.append((p,'composite'))
            continue
        if p%8 != 3 or legendre(5,p) != -1:
            continue
        if pow(2,M_BIG,p) != 1 or fib_mod(N_BIG,p) != 0:
            bad.append((p,'pool_order_property'))
            continue
        mult2=math.gcd(M_BIG,p-1)
        f_mult2=factor_over(mult2,list(fm))
        o2=multiplicative_order(2,p,f_mult2)
        mult_rho=math.gcd(N_BIG,p+1)
        f_mult_rho=factor_over(mult_rho,list(fn))
        rho=fibonacci_rank_from_multiple(p,mult_rho,f_mult_rho)
        fpm_full={int(q):int(e) for q,e in sympy_factorint(p-1).items()}
        o5=multiplicative_order(5,p,fpm_full)
        records.append({'p':p,'o2':o2,'o5':o5,'rho':rho,
                        'o5_divides_M':M_BIG%o5==0,
                        'v2_o2':v2(o2),'v2_o5':v2(o5),'v2_rho':v2(rho)})
    if bad:
        raise RuntimeError(f'Pool validation failures: {bad[:10]} total={len(bad)}')

    classes=Counter((r['v2_o2'],r['v2_o5'],r['v2_rho']) for r in records)
    records=[r for r in records
             if (r['v2_o2'],r['v2_o5'],r['v2_rho'])==(1,1,2)
             and r['o5_divides_M']]
    primes=[r['p'] for r in records]
    minus_values=[math.lcm(r['o2'],r['o5']) for r in records]
    plus_values=[r['rho'] for r in records]
    fac_minus=merge_lcm_factorization(minus_values,list(fm))
    fac_plus=merge_lcm_factorization(plus_values,list(fn))
    Lminus=from_factorization(fac_minus)
    Lplus=from_factorization(fac_plus)
    if math.gcd(Lminus,Lplus)!=2:
        raise RuntimeError(f'Unexpected gcd(Lminus,Lplus)={math.gcd(Lminus,Lplus)}')
    rows=build_rows(primes,fac_minus,fac_plus)
    group_bits=sum(math.log2(r['modulus']) for r in rows)
    stats={'source':SOURCE_URL,'pool_count':len(pool),
           'eligible_before_v2_filter':sum(classes.values()),
           'v2_classes':{str(k):v for k,v in sorted(classes.items())},
           'selected_class':{'v2':(1,1,2),'o5_divides_M':True},
           'variables':len(primes),'Lminus_bits':Lminus.bit_length(),
           'Lplus_bits':Lplus.bit_length(),'gcd_L':math.gcd(Lminus,Lplus),
           'coordinate_rows':len(rows),'ambient_group_bits':group_bits,
           'naive_surplus_bits':len(primes)-group_bits,
           'Lminus_factorization':fac_minus,'Lplus_factorization':fac_plus}
    (OUT/'analysis.json').write_text(json.dumps(stats,indent=2,sort_keys=True)+'\n')
    print(json.dumps(stats,indent=2,sort_keys=True),flush=True)

    time_limit=float(os.environ.get('BPSW_TIME_LIMIT','1200'))
    seeds=[int(x) for x in os.environ.get('BPSW_SEEDS','1,7,23').split(',') if x]
    chosen=[]
    status=None
    response_stats=''
    for seed in seeds:
        print(f'CP-SAT attempt seed={seed} limit={time_limit}s',flush=True)
        status,chosen,response_stats=solve_subset(primes,rows,time_limit,seed)
        print(response_stats,flush=True)
        if chosen:
            break
    if not chosen:
        (OUT/'no_candidate.txt').write_text(f'status={status}\n{response_stats}\n')
        return 2

    factors=[primes[i] for i in chosen]
    n=math.prod(factors)
    print(f'FOUND subset size={len(factors)} n_bits={n.bit_length()} n_digits={len(str(n))}',flush=True)
    structural={'subset_size':len(factors),'subset_odd':len(factors)%2==1,
                'n_mod_Lminus':n%Lminus,'n_mod_Lplus':n%Lplus,
                'all_p_mod8_3':all(p%8==3 for p in factors),
                'all_legendre5_minus':all(legendre(5,p)==-1 for p in factors)}
    D,P,Q=method_a_star(n)
    base2_ok,base2_branch=strong_prp(n,2)
    lucas_ok,lucas_branch=strong_lucas(n,P,Q,D)
    U_np1,V_np1=lucas_uv(P,Q,n+1,n)
    v_target=(2*Q)%n
    qpow=pow(Q,(n+1)//2,n)
    jac_q=jacobi(Q,n)
    q_target=(Q*jac_q)%n
    verification={'method_A_star':{'D':D,'P':P,'Q':Q},
                  'strong_base2':base2_ok,'strong_base2_branch':base2_branch,
                  'strong_lucas':lucas_ok,'strong_lucas_branch':lucas_branch,
                  'U_n_plus_1_mod_n':str(U_np1),'V_n_plus_1_mod_n':str(V_np1),
                  'V_target':str(v_target),'V_condition':V_np1==v_target,
                  'Q_power_mod_n':str(qpow),'Q_power_target':str(q_target),
                  'Q_power_condition':qpow==q_target,
                  'jacobi_D_n':jacobi(D,n),'jacobi_Q_n':jac_q}
    all_ok=(structural['subset_odd'] and structural['n_mod_Lminus']==1
            and structural['n_mod_Lplus']==Lplus-1 and D==5 and P==5 and Q==5
            and base2_ok and lucas_ok and U_np1==0 and V_np1==v_target
            and qpow==q_target)
    result={'all_checks_pass':all_ok,'n':str(n),'n_bits':n.bit_length(),
            'n_digits':len(str(n)),'factors':[str(p) for p in factors],
            'factor_count':len(factors),'structural':structural,
            'verification':verification,'analysis':stats,
            'solver_response_stats':response_stats}
    (OUT/'candidate.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    (OUT/'candidate_factors.txt').write_text('\n'.join(map(str,factors))+'\n')
    (OUT/'candidate_n.txt').write_text(str(n)+'\n')
    print(json.dumps({k:result[k] for k in ('all_checks_pass','n_bits','n_digits','factor_count','structural','verification')},indent=2),flush=True)
    if not all_ok:
        raise RuntimeError('Candidate failed independent enhanced-BPSW verification')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
