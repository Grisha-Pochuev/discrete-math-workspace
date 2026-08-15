#!/usr/bin/env python3
from __future__ import annotations

import argparse, collections, hashlib, json, math, random, time
from pathlib import Path
from typing import Iterable

from ortools.sat.python import cp_model
from sympy import factorint, primitive_root, jacobi_symbol


def v2(n: int) -> int:
    return (n & -n).bit_length() - 1


def lcm_many(xs: Iterable[int]) -> int:
    z = 1
    for x in xs:
        z = math.lcm(z, int(x))
    return z


def phi_pp(q: int, e: int) -> int:
    return (q - 1) * q ** (e - 1)


def pool_score(rs: list[dict]) -> dict:
    lp = lcm_many(r['plus_odd'] for r in rs)
    lm = lcm_many(r['minus_odd'] for r in rs)
    fp = {int(q): int(e) for q, e in factorint(lp).items()}
    fm = {int(q): int(e) for q, e in factorint(lm).items()}
    ent = sum(math.log2(phi_pp(q, e)) for q, e in fp.items()) + sum(math.log2(phi_pp(q, e)) for q, e in fm.items())
    return {'count': len(rs), 'lp': lp, 'lm': lm, 'entropy': ent,
            'surplus': len(rs) - ent, 'gcd': math.gcd(lp, lm),
            'nfactors': len(fp) + len(fm)}


def coord_users(rs: list[dict]):
    lp = lcm_many(r['plus_odd'] for r in rs)
    lm = lcm_many(r['minus_odd'] for r in rs)
    out = []
    for side, L in [('p', lp), ('m', lm)]:
        for q, e in factorint(L).items():
            q, e = int(q), int(e)
            pe = q ** e
            field = 'plus_odd' if side == 'p' else 'minus_odd'
            users = [r for r in rs if r[field] % pe == 0]
            out.append((side, q, e, users, math.log2(phi_pp(q, e))))
    return out


def generate_pools(groups: dict, max_pools: int = 40):
    candidates = []
    for key, base in groups.items():
        cur = list(base)
        for step in range(61):
            if len(cur) < 12:
                break
            sc = pool_score(cur)
            candidates.append((sc['surplus'], sc['count'], key, f'greedy-{step}', list(cur), sc))
            opts = []
            for side, q, e, users, cost in coord_users(cur):
                opts.append((cost - len(users), cost / max(1, len(users)), side, q, e, users))
            if not opts:
                break
            opts.sort(reverse=True, key=lambda z: (z[0], z[1]))
            users = opts[0][-1]
            kill = {r['p'] for r in users}
            nxt = [r for r in cur if r['p'] not in kill]
            if not nxt or len(nxt) == len(cur):
                break
            cur = nxt
        for threshold in [1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64]:
            cur = list(base)
            changed = True
            while changed and len(cur) >= 12:
                changed = False
                bad = []
                for side, q, e, users, cost in coord_users(cur):
                    if len(users) < threshold * max(1.0, cost / 8.0):
                        bad.extend(users)
                if bad:
                    kill = {r['p'] for r in bad}
                    nxt = [r for r in cur if r['p'] not in kill]
                    if len(nxt) < len(cur):
                        cur = nxt
                        changed = True
            if len(cur) >= 12:
                sc = pool_score(cur)
                candidates.append((sc['surplus'], sc['count'], key, f'core-{threshold}', cur, sc))
    seen, out = set(), []
    candidates.sort(reverse=True, key=lambda z: (z[0], z[1]))
    for item in candidates:
        sig = hashlib.sha256(','.join(str(r['p']) for r in item[4]).encode()).hexdigest()
        if sig in seen:
            continue
        seen.add(sig)
        out.append(item)
        if len(out) >= max_pools:
            break
    return out


def build_log_table(mod: int):
    g = int(primitive_root(mod))
    fm = factorint(mod)
    if len(fm) != 1:
        raise ValueError(mod)
    q, e = next(iter(fm.items()))
    q, e = int(q), int(e)
    order = phi_pp(q, e)
    tab, value = {}, 1
    for k in range(order):
        tab[value] = k
        value = (value * g) % mod
    if len(tab) != order or value != 1:
        raise ArithmeticError(('logtable', mod, len(tab), order, value))
    return g, order, tab


def make_coordinates(rs: list[dict]):
    sc = pool_score(rs)
    if sc['gcd'] != 1:
        raise ValueError(f"plus/minus overlap {sc['gcd']}")
    coords = []
    for side, L in [('plus', sc['lp']), ('minus', sc['lm'])]:
        for q, e in factorint(L).items():
            q, e = int(q), int(e)
            mod = q ** e
            g, order, tab = build_log_table(mod)
            coeff = []
            for r in rs:
                residue = r['p'] % mod
                if residue not in tab:
                    raise ArithmeticError(('nonunit', r['p'], mod))
                coeff.append(tab[residue])
            target = 0 if side == 'plus' else tab[(-1) % mod]
            coords.append({'side': side, 'q': q, 'e': e, 'modulus': mod,
                           'order': order, 'generator': g,
                           'coeff': coeff, 'target': target})
    return sc, coords


def mat_mul(A, B, n):
    return ((A[0] * B[0] + A[1] * B[2]) % n,
            (A[0] * B[1] + A[1] * B[3]) % n,
            (A[2] * B[0] + A[3] * B[2]) % n,
            (A[2] * B[1] + A[3] * B[3]) % n)


def mat_pow(M, k, n):
    R = (1, 0, 0, 1)
    while k:
        if k & 1:
            R = mat_mul(R, M, n)
        M = mat_mul(M, M, n)
        k >>= 1
    return R


def strong_base(n, a):
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    x = pow(a, d, n)
    if x in (1, n - 1):
        return True
    for _ in range(s - 1):
        x = x * x % n
        if x == n - 1:
            return True
    return False


def strong_lucas(n, P, Q):
    k = n + 1
    s = v2(k)
    d = k >> s
    M = (P % n, (-Q) % n, 1, 0)
    cur = mat_pow(M, d, n)
    if cur[2] % n == 0:
        return True
    for _ in range(s):
        if (cur[0] + cur[3]) % n == 0:
            return True
        cur = mat_mul(cur, cur, n)
    return False


def verify_candidate(rs, chosen):
    ps = [rs[i]['p'] for i in chosen]
    n = math.prod(ps)
    errors = []
    if len(ps) < 2 or len(ps) % 2 != 1:
        errors.append('cardinality')
    if int(jacobi_symbol(5, n)) != -1:
        errors.append('jacobi5')
    for i in chosen:
        r = rs[i]
        p = r['p']
        m = n // p
        if m % r['c'] != 1:
            errors.append(f'local-c-{p}')
        if (n - 1) % r['o2'] != 0:
            errors.append(f'ord2-{p}')
        if (n + 1) % r['rho'] != 0:
            errors.append(f'rho-{p}')
    if not strong_base(n, 2):
        errors.append('strong-base2')
    if not strong_lucas(n, 5, 5):
        errors.append('strong-lucas')
    M = (5 % n, (-5) % n, 1, 0)
    A = mat_pow(M, n + 1, n)
    U = A[2] % n
    V = (A[0] + A[3]) % n
    if U != 0:
        errors.append('U_n+1')
    if V != 10 % n:
        errors.append('V_n+1')
    euler = pow(5, (n + 1) // 2, n)
    if euler != (5 * int(jacobi_symbol(5, n))) % n:
        errors.append('Euler-Q')
    return n, ps, errors, {'U': U, 'V': V, 'euler': euler}


def solve_pool(rs: list[dict], seed: int, seconds: int, workers: int, card_delta: int):
    sc, coords = make_coordinates(rs)
    model = cp_model.CpModel()
    x = [model.NewBoolVar(f'x{i}') for i in range(len(rs))]
    for ci, c in enumerate(coords):
        coeff, order, target = c['coeff'], c['order'], c['target']
        maxsum = sum(coeff)
        kval = model.NewIntVar((-target) // order - 1,
                                (maxsum - target) // order + 1, f'k{ci}')
        model.Add(sum(coeff[i] * x[i] for i in range(len(rs))) - target == order * kval)
    kmod = rs[0]['kmod']
    total = model.NewIntVar(3, len(rs), 'total')
    model.Add(total == sum(x))
    z = model.NewIntVar(0, len(rs) // max(1, kmod) + 2, 'cardz')
    model.Add(total == 1 + kmod * z)
    mid = len(rs) // 2 + card_delta
    while (mid - 1) % kmod:
        mid += 1
    lo, hi = max(3, mid - 4 * kmod), min(len(rs), mid + 4 * kmod)
    while (lo - 1) % kmod:
        lo += 1
    while (hi - 1) % kmod:
        hi -= 1
    if lo <= hi:
        model.Add(total >= lo)
        model.Add(total <= hi)
    rng = random.Random(seed)
    weights = [rng.randint(-1000, 1000) for _ in rs]
    model.Maximize(sum(weights[i] * x[i] for i in range(len(rs))))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(seconds)
    solver.parameters.num_search_workers = workers
    solver.parameters.random_seed = seed
    solver.parameters.log_search_progress = True
    status = solver.Solve(model)
    chosen = []
    if status in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        chosen = [i for i, xv in enumerate(x) if solver.Value(xv)]
    return {'status': solver.StatusName(status), 'wall_time': solver.WallTime(),
            'branches': solver.NumBranches(), 'conflicts': solver.NumConflicts(),
            'score': sc, 'coordinates': len(coords), 'chosen': chosen}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--records', default='enhanced-bpsw/greene-records.jsonl')
    ap.add_argument('--pool-rank', type=int, default=0)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--seconds', type=int, default=3000)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--card-delta', type=int, default=0)
    ap.add_argument('--output', default='enhanced-bpsw/solution.json')
    ap.add_argument('--max-pools', type=int, default=40)
    args = ap.parse_args()
    records = [json.loads(line) for line in open(args.records) if line.strip()]
    groups = collections.defaultdict(list)
    for r in records:
        groups[(r['a2'], r['arho'], r['ac'], r['residue2'])].append(r)
    pools = generate_pools(groups, args.max_pools)
    if args.pool_rank >= len(pools):
        raise SystemExit(f'pool rank {args.pool_rank} >= {len(pools)}')
    _, _, key, label, rs, score = pools[args.pool_rank]
    print(json.dumps({'selected_pool_rank': args.pool_rank, 'key': key,
                      'label': label, 'score': score,
                      'top_pools': [{'rank': i, 'key': p[2], 'label': p[3], 'score': p[5]}
                                    for i, p in enumerate(pools[:15])]}, indent=2), flush=True)
    started = time.time()
    result = solve_pool(rs, args.seed, args.seconds, args.workers, args.card_delta)
    result.update({'pool_rank': args.pool_rank, 'key': list(key), 'label': label,
                   'seed': args.seed, 'card_delta': args.card_delta,
                   'elapsed': time.time() - started})
    if result['chosen']:
        n, ps, errors, checks = verify_candidate(rs, result['chosen'])
        result['candidate'] = {'n': str(n), 'digits': len(str(n)),
                               'prime_factors': ps, 'factor_count': len(ps),
                               'errors': errors, 'checks': checks}
        print('CANDIDATE', json.dumps(result['candidate'], indent=2), flush=True)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'chosen'},
                     indent=2, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
