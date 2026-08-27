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
            aa_s, aa_a = [], []
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


def gf2_rows(coords, n):
    out = []
    for m, aa, b, meta in coords:
        mask = 0
        for i, a in enumerate(aa):
            if a & 1:
                mask |= 1 << i
        out.append((mask, b & 1, meta))
    return out


def gf2_rref(rows):
    basis = {}
    for mask, rhs, _ in rows:
        while mask:
            p = (mask & -mask).bit_length() - 1
            if p in basis:
                mask ^= basis[p][0]
                rhs ^= basis[p][1]
            else:
                basis[p] = (mask, rhs)
                break
        if not mask and rhs:
            raise RuntimeError('xor-inconsistent')
    piv = sorted(basis)
    for p in reversed(piv):
        rm, rr = basis[p]
        for q in piv:
            if q == p:
                continue
            qm, qr = basis[q]
            if (qm >> p) & 1:
                basis[q] = (qm ^ rm, qr ^ rr)
    return basis


def core_check(data_path):
    P, F, maxe, targets, coords, split = build(data_path)
    for i, p in enumerate(P):
        for r, e in F[i].items():
            E = maxe[r]
            if targets[(r, E)] % (r ** e) != p % (r ** e):
                raise RuntimeError(('local-target', i, r, e, E))
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
    xr = gf2_rows(coords, len(P))
    basis = gf2_rref(xr)
    if len(basis) != 119:
        raise RuntimeError(('xor-rank', len(basis)))
    m0, a0, b0, _ = coords[0]
    if m0 != 2 or b0 != 1 or any((a & 1) != 1 for a in a0):
        raise RuntimeError('odd-row')
    print('CHECK n=%d bases=%d coords=%d rows=%d xor=%d maxq=%d' %
          (len(P), len(maxe), len(coords), len(split), len(basis), max(q for q, _, _, _ in split)))
    return 0


def xor_hint(coords, split, n, seed, steps=24000):
    import numpy as np
    rng = random.Random(seed ^ 0x62A5D19)
    basis = gf2_rref(gf2_rows(coords, n))
    piv = set(basis)
    free = [i for i in range(n) if i not in piv]
    part = 0
    for p, (_, rhs) in basis.items():
        if rhs:
            part |= 1 << p
    moves = []
    for f in free:
        mm = 1 << f
        for p, (row, _) in basis.items():
            if (row >> f) & 1:
                mm |= 1 << p
        moves.append(mm)

    S = [z for z in split if z[0] > 2]
    qv = np.array([z[0] for z in S], dtype=np.int64)
    bv = np.array([z[2] for z in S], dtype=np.int64)
    A = np.array([z[1] for z in S], dtype=np.int64)
    w = np.log2(qv.astype(float))

    def to_array(mask):
        return np.fromiter(((mask >> i) & 1 for i in range(n)), dtype=np.int64, count=n)

    def score(r):
        ang = np.pi * r / qv
        return float(np.sum(w * (r != 0)) + 0.06 * np.sum(w * np.sin(ang) ** 2))

    best = None
    best_x = None
    per = max(1000, steps // 3)
    for _ in range(3):
        mask = part
        for mv in moves:
            if rng.getrandbits(1):
                mask ^= mv
        x = to_array(mask)
        for _retry in range(20):
            k = int(x.sum())
            if 440 <= k <= 590:
                break
            mask = part
            for mv in moves:
                if rng.getrandbits(1):
                    mask ^= mv
            x = to_array(mask)
        R = (A @ x - bv) % qv
        C = score(R)
        if best is None or C < best:
            best, best_x = C, x.copy()
        temp0 = 1.1
        for it in range(per):
            mi = rng.randrange(len(moves))
            mm = moves[mi]
            inds = []
            t = mm
            while t:
                low = t & -t
                inds.append(low.bit_length() - 1)
                t ^= low
            inds = np.asarray(inds, dtype=np.int64)
            signs = 1 - 2 * x[inds]
            R2 = (R + A[:, inds] @ signs) % qv
            C2 = score(R2)
            frac = it / per
            temp = max(0.02, temp0 * (1.0 - frac))
            k2 = int(x.sum() + signs.sum())
            if 430 <= k2 <= 600 and (C2 <= C or rng.random() < math.exp(max(-50.0, (C - C2) / temp))):
                x[inds] = 1 - x[inds]
                R, C = R2, C2
                if C < best:
                    best, best_x = C, x.copy()
    exact = int(np.sum(((A @ best_x - bv) % qv) == 0))
    return [int(v) for v in best_x.tolist()], float(best), exact


def add_xor_constraints(model, x, coords):
    count = 0
    for m, aa, b, meta in coords:
        lits = [x[i] for i, a in enumerate(aa) if a & 1]
        target = b & 1
        if not lits:
            if target:
                model.AddBoolOr([])
            continue
        if target:
            model.AddBoolXOr(lits)
        else:
            model.AddBoolXOr([lits[0].Not()] + lits[1:])
        count += 1
    return count


def add_mod_rows(model, x, coords, split, form):
    rows = split if form == 's' else coords
    count = 0
    for ri, row in enumerate(rows):
        q, aa, b, meta = row
        if q == 2:
            continue
        nz = [(a, x[i]) for i, a in enumerate(aa) if a]
        total = sum(a for a, _ in nz)
        zmax = max(0, (total - b) // q)
        z = model.NewIntVar(0, zmax, 'z%d' % ri)
        model.Add(sum(a * v for a, v in nz) - q * z == b)
        count += 1
    return count


def solve(data_path, seed, seconds, out_path, form='s', mode=0, fix_count=12):
    from ortools.sat.python import cp_model

    P, F, maxe, targets, coords, split = build(data_path)
    n = len(P)
    if form not in ('s', 'c'):
        raise RuntimeError(('form', form))

    hint, hscore, hexact = xor_hint(coords, split, n, seed)
    hk = sum(hint)
    model = cp_model.CpModel()
    x = [model.NewBoolVar('x%d' % i) for i in range(n)]
    k = model.NewIntVar(430, 600, 'k')
    model.Add(k == sum(x))
    nxor = add_xor_constraints(model, x, coords)
    nmod = add_mod_rows(model, x, coords, split, form)

    rng = random.Random(seed ^ 0xB17F00D)
    fixed = sorted(rng.sample(range(n), min(max(0, fix_count), n)))
    for i in fixed:
        model.Add(x[i] == hint[i])
    for i, v in enumerate(hint):
        model.AddHint(x[i], v)
    model.AddHint(k, hk)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(seconds)
    solver.parameters.num_search_workers = 4
    solver.parameters.random_seed = int(seed)
    solver.parameters.randomize_search = True
    solver.parameters.permute_variable_randomly = True
    solver.parameters.permute_presolve_constraint_order = True
    solver.parameters.stop_after_first_solution = True
    if mode == 1:
        solver.parameters.search_branching = cp_model.RANDOMIZED_SEARCH
    elif mode == 2:
        solver.parameters.use_ls_only = True
        solver.parameters.use_feasibility_jump = True
    elif mode == 3:
        solver.parameters.search_branching = cp_model.PORTFOLIO_WITH_QUICK_RESTART_SEARCH
    elif mode != 0:
        raise RuntimeError(('mode', mode))

    t0 = time.time()
    status = solver.Solve(model)
    elapsed = time.time() - t0
    name = solver.StatusName(status)
    lines = [
        'status=%s' % name,
        'seed=%d' % seed,
        'sec=%.6f' % elapsed,
        'form=%s' % form,
        'mode=%d' % mode,
        'fix=%d' % len(fixed),
        'xor=%d' % nxor,
        'mod=%d' % nmod,
        'hint_k=%d' % hk,
        'hint_score=%.6f' % hscore,
        'hint_exact=%d' % hexact,
        'branches=%d' % solver.NumBranches(),
        'conflicts=%d' % solver.NumConflicts(),
        'wall=%.6f' % solver.WallTime(),
    ]
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        sel = [i for i in range(n) if solver.Value(x[i])]
        if len(sel) < 3 or len(sel) % 2 != 1:
            raise RuntimeError(('count-parity', len(sel)))
        prod = 1
        for i in sel:
            prod *= P[i]
        for i in sel:
            p = P[i]
            if (prod - 1) % (p - 1) != 0 or (prod + 1) % (p + 1) != 0:
                raise RuntimeError(('verify-local', i, p))
        for i, p in enumerate(P):
            for r, e in F[i].items():
                if prod % (r ** e) != targets[(r, maxe[r])] % (r ** e):
                    raise RuntimeError(('verify-global', i, r, e))
        lines += [
            'verified=1',
            'k=%d' % len(sel),
            'indices=' + ','.join(map(str, sel)),
            'factors=' + ','.join(str(P[i]) for i in sel),
            'N=' + str(prod),
        ]
        rc = 0
        print('FOUND k=%d form=%s mode=%d sec=%.3f' % (len(sel), form, mode, elapsed))
    else:
        lines += ['verified=0', 'k=-1']
        rc = 2
        print('END status=%s form=%s mode=%d sec=%.3f br=%d cf=%d hint=%d/%d' %
              (name, form, mode, elapsed, solver.NumBranches(), solver.NumConflicts(), hexact, len([z for z in split if z[0] > 2])))

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    return rc


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[2] == 'check':
        raise SystemExit(core_check(sys.argv[1]))
    if len(sys.argv) in (6, 7, 8):
        data, seed, sec, out, form = sys.argv[1:6]
        mode = int(sys.argv[6]) if len(sys.argv) >= 7 else 0
        fix = int(sys.argv[7]) if len(sys.argv) >= 8 else 12
        raise SystemExit(solve(data, int(seed), float(sec), out, form, mode, fix))
    print('usage: b.py DATA check | b.py DATA SEED SEC OUT FORM [MODE [FIX]]', file=sys.stderr)
    raise SystemExit(1)
