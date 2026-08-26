#!/usr/bin/env python3
import math, random, sys, time
from collections import defaultdict

sys.set_int_max_str_digits(1000000)


def primes_upto(n):
    a = []
    for q in range(2, n + 1):
        ok = True
        d = 2
        while d * d <= q:
            if q % d == 0:
                ok = False
                break
            d += 1
        if ok:
            a.append(q)
    return a


def distinct_pf(n):
    out = []
    d = 2
    while d * d <= n:
        if n % d == 0:
            out.append(d)
            while n % d == 0:
                n //= d
        d += 1 if d == 2 else 2
    if n > 1:
        out.append(n)
    return out


def prime_power_parts(n):
    out = []
    d = 2
    while d * d <= n:
        if n % d == 0:
            z = 1
            while n % d == 0:
                n //= d
                z *= d
            out.append(z)
        d += 1 if d == 2 else 2
    if n > 1:
        out.append(n)
    return out


def primitive_root_prime_power(r, e):
    h = r ** e
    m = (r - 1) * r ** (e - 1)
    fs = distinct_pf(m)
    for g in range(2, h):
        if math.gcd(g, h) != 1:
            continue
        if all(pow(g, m // q, h) != 1 for q in fs):
            return g
    raise RuntimeError((r, e))


def dlog_table(h, g, m):
    tab = {}
    z = 1
    for a in range(m):
        if z in tab:
            raise RuntimeError(('cycle', h, g, a))
        tab[z] = a
        z = (z * g) % h
    if z != 1 or len(tab) != m:
        raise RuntimeError(('bad-cycle', h, g, m, len(tab)))
    return tab


def two_table(e):
    h = 1 << e
    m = 1 << (e - 2)
    tab = {}
    z = 1
    for a in range(m):
        tab[z] = a
        z = (z * 5) % h
    if z != 1 or len(tab) != m:
        raise RuntimeError(('bad-two-cycle', e))
    return tab


def two_coords(u, e, tab):
    h = 1 << e
    u %= h
    if u % 2 == 0:
        raise RuntimeError(('nonunit2', u, e))
    s = 0 if u % 4 == 1 else 1
    v = u if s == 0 else (-u) % h
    return s, tab[v]


def build(data_path):
    P = [int(s) for s in open(data_path, 'r', encoding='utf-8').read().split()]
    if len(P) != 1029 or len(set(P)) != len(P):
        raise RuntimeError(('data-count', len(P), len(set(P))))
    small = primes_upto(653)
    F = []
    maxe = defaultdict(int)
    for p in P:
        x = (p * p - 1) // 2
        f = {}
        for r in small:
            e = 0
            while x % r == 0:
                x //= r
                e += 1
            if e:
                f[r] = e
                if e > maxe[r]:
                    maxe[r] = e
        if x != 1:
            raise RuntimeError(('large-factor', p, x))
        F.append(f)
    if len(maxe) != 119 or max(maxe) != 653:
        raise RuntimeError(('basis', len(maxe), max(maxe)))

    coords = []
    targets = {}
    for r, E in sorted(maxe.items()):
        h = r ** E
        active = [i for i, f in enumerate(F) if f.get(r, 0) >= E]
        vals = {P[i] % h for i in active}
        if len(vals) != 1:
            raise RuntimeError(('target-conflict', r, E, len(vals)))
        t = next(iter(vals))
        targets[(r, E)] = t
        if r == 2:
            if E < 3:
                raise RuntimeError(('two-exp', E))
            tab = two_table(E)
            bs, ba = two_coords(t, E, tab)
            aa_s = []
            aa_a = []
            for p in P:
                s, a = two_coords(p, E, tab)
                aa_s.append(s)
                aa_a.append(a)
            coords.append((2, aa_s, bs, (r, E, 0)))
            coords.append((1 << (E - 2), aa_a, ba, (r, E, 1)))
        else:
            m = (r - 1) * r ** (E - 1)
            g = primitive_root_prime_power(r, E)
            tab = dlog_table(h, g, m)
            try:
                aa = [tab[p % h] for p in P]
                b = tab[t]
            except KeyError as exc:
                raise RuntimeError(('dlog-miss', r, E, int(exc.args[0]))) from exc
            for p, a in zip(P, aa):
                if pow(g, a, h) != p % h:
                    raise RuntimeError(('reconstruct', r, E, p))
            coords.append((m, aa, b, (r, E, 0)))
    if len(coords) != 120:
        raise RuntimeError(('coord-count', len(coords)))

    split = []
    seen = set()
    for m, aa, b, meta in coords:
        for q in prime_power_parts(m):
            key = (q, b % q, tuple(a % q for a in aa))
            if key in seen:
                raise RuntimeError(('duplicate-row', meta, q))
            seen.add(key)
            split.append((q, [a % q for a in aa], b % q, meta))
    if len(split) != 314:
        raise RuntimeError(('split-count', len(split)))
    return P, F, maxe, targets, coords, split


def core_check(data_path):
    P, F, maxe, targets, coords, split = build(data_path)
    for i, p in enumerate(P):
        for r, e in F[i].items():
            E = maxe[r]
            if e == E and p % (r ** E) != targets[(r, E)]:
                raise RuntimeError(('local-target', i, r, E))
    rng = random.Random(62026)
    for _ in range(40):
        x = [rng.getrandbits(1) for _ in P]
        lhs0 = [sum(a * z for a, z in zip(aa, x)) % m == b for m, aa, b, _ in coords]
        lhs1 = []
        pos = 0
        for m, aa, b, _ in coords:
            ok = True
            for q in prime_power_parts(m):
                q0, qa, qb, _ = split[pos]
                if q0 != q or sum(a * z for a, z in zip(qa, x)) % q != qb:
                    ok = False
                pos += 1
            lhs1.append(ok)
        if lhs0 != lhs1:
            raise RuntimeError('split-equivalence')
    print('CHECK n=%d bases=%d coords=%d rows=%d maxq=%d' %
          (len(P), len(maxe), len(coords), len(split), max(q for q, _, _, _ in split)))
    return 0


def solve(data_path, k, seed, seconds, out_path):
    from ortools.sat.python import cp_model

    P, F, maxe, targets, coords, split = build(data_path)
    n = len(P)
    if not (0 <= k <= n):
        raise RuntimeError(('k', k))

    model = cp_model.CpModel()
    x = [model.NewBoolVar('x%d' % i) for i in range(n)]
    model.Add(sum(x) == k)

    for ri, (q, aa, b, meta) in enumerate(split):
        nz = [(a, x[i]) for i, a in enumerate(aa) if a]
        z = model.NewIntVar(0, k, 'z%d' % ri)
        model.Add(sum(a * v for a, v in nz) - q * z == b)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(seconds)
    solver.parameters.num_search_workers = 4
    solver.parameters.random_seed = int(seed)
    solver.parameters.randomize_search = True
    solver.parameters.log_search_progress = False
    t0 = time.time()
    status = solver.Solve(model)
    elapsed = time.time() - t0
    name = solver.StatusName(status)

    lines = ['status=%s' % name, 'k=%d' % k, 'seed=%d' % seed, 'sec=%.6f' % elapsed]
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        sel = [i for i in range(n) if solver.Value(x[i])]
        if len(sel) != k:
            raise RuntimeError(('count', len(sel), k))
        prod = 1
        for i in sel:
            prod *= P[i]
        for i in sel:
            p = P[i]
            if (prod - 1) % (p - 1) != 0 or (prod + 1) % (p + 1) != 0:
                raise RuntimeError(('verify-local', i, p))
        for (r, E), t in targets.items():
            if prod % (r ** E) != t:
                raise RuntimeError(('verify-global', r, E))
        lines += [
            'verified=1',
            'indices=' + ','.join(map(str, sel)),
            'factors=' + ','.join(str(P[i]) for i in sel),
            'N=' + str(prod),
        ]
        rc = 0
        print('FOUND k=%d sec=%.3f' % (k, elapsed))
    else:
        lines.append('verified=0')
        rc = 2
        print('END status=%s k=%d sec=%.3f' % (name, k, elapsed))

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    return rc


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[2] == 'check':
        raise SystemExit(core_check(sys.argv[1]))
    if len(sys.argv) == 6:
        raise SystemExit(solve(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4]), sys.argv[5]))
    print('usage: b.py DATA check | b.py DATA K SEED SEC OUT', file=sys.stderr)
    raise SystemExit(1)
