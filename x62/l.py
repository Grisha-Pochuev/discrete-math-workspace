#!/usr/bin/env python3
import base64, random, sys, time
import b
from ortools.sat.python import cp_model

X0 = 'NzNR/koBLPR3Ehd+FNSqOQpI3haHo6pNmXyJb2MmIduX0kNGynjdFDdDm8CJuSepuhgkAHJzF+6LJL02+jijGCbRrJVTlClcwx3t0kC7rGGMF+dW3gLYLWU9rSJgfmNx0VszsfJMTarMx74XzXcJjA8Ws7VJ99cQ1MbS2rvP330b'

def pbase(q):
    for p in range(2, int(q ** .5) + 2):
        if q % p == 0:
            z = q
            while z % p == 0:
                z //= p
            if z == 1:
                return p
    return q

def exponent(q, p):
    e = 0
    while q > 1:
        if q % p:
            raise RuntimeError(('power', q, p))
        q //= p
        e += 1
    return e

def seedvec(n):
    z = base64.b64decode(X0)
    x = [(z[i >> 3] >> (i & 7)) & 1 for i in range(n)]
    if sum(x) != 519:
        raise RuntimeError(('seed', sum(x)))
    return x

def add_row(model, v, rem, add, x0, row, mod, t, tag):
    _, aa0, target0, _ = row
    aa = [a % mod for a in aa0]
    cur = sum(aa[i] for i, z in enumerate(x0) if z) % mod
    rhs = (target0 - cur) % mod
    ar = [(-aa[i]) % mod for i in rem]
    ad = [aa[i] for i in add]
    sr = sorted(ar)
    sa = sorted(ad)
    lo = sum(sr[:t]) + sum(sa[:t])
    hi = sum(sr[-t:]) + sum(sa[-t:])
    zlo = (lo - rhs + mod - 1) // mod
    zhi = (hi - rhs) // mod
    if zlo > zhi:
        model.AddBoolOr([])
        return
    z = model.NewIntVar(zlo, zhi, tag)
    model.Add(sum(ar[j] * v[j] for j in range(len(rem)) if ar[j]) +
              sum(ad[j] * v[len(rem) + j] for j in range(len(add)) if ad[j]) - mod * z == rhs)

def verify(rows3, rows5, levels, x):
    sel = [i for i, z in enumerate(x) if z]
    for q, a, target, meta in rows3:
        if sum(a[i] for i in sel) % q != target:
            raise RuntimeError(('v3', q, meta))
    for ri, lev in enumerate(levels):
        if lev:
            q, a, target, meta = rows5[ri]
            m = 5 ** lev
            if sum((a[i] % m) for i in sel) % m != target % m:
                raise RuntimeError(('v5', ri, lev, q, meta))

def solve(path, seed, seconds, out, t, style, mode, batch):
    P, _, _, _, _, split = b.build(path)
    n = len(P)
    x0 = seedvec(n)
    rows3 = [z for z in split if z[0] & 1 and pbase(z[0]) == 3]
    rows5 = [z for z in split if z[0] & 1 and pbase(z[0]) == 5]
    if len(rows3) != 57 or len(rows5) != 29:
        raise RuntimeError(('rows', len(rows3), len(rows5)))
    rem = [i for i, z in enumerate(x0) if z]
    add = [i for i, z in enumerate(x0) if not z]
    levels = []
    tasks = []
    for ri, (q, a, target, meta) in enumerate(rows5):
        E = exponent(q, 5)
        d = sum(a[i] for i in rem) - target
        lev = 0
        for e in range(1, E + 1):
            if d % (5 ** e) == 0:
                lev = e
            else:
                break
        levels.append(lev)
        for e in range(lev + 1, E + 1):
            tasks.append((e, ri))
    if sum(levels) != 16 or len(tasks) != 22:
        raise RuntimeError(('digits', sum(levels), len(tasks)))
    rng = random.Random(seed ^ 0x519625)
    if style == 0:
        tasks.sort(key=lambda z: (z[0], sum(v != 0 for v in rows5[z[1]][1]), z[1]))
    elif style == 1:
        tasks.sort(key=lambda z: (z[0], -sum(v != 0 for v in rows5[z[1]][1]), z[1]))
    elif style == 2:
        rng.shuffle(tasks)
    elif style == 3:
        tasks.sort(key=lambda z: (-z[0], sum(v != 0 for v in rows5[z[1]][1]), z[1]))
    elif style == 4:
        groups = {}
        for e, ri in tasks:
            groups.setdefault(e, []).append((e, ri))
        tasks = []
        for e in sorted(groups):
            g = sorted(groups[e], key=lambda z: sum(v != 0 for v in rows5[z[1]][1]))
            while g:
                tasks.append(g.pop(0))
                if g:
                    tasks.append(g.pop())
    else:
        raise RuntimeError(('style', style))
    cuts = list(range(0, len(tasks), batch)) + [len(tasks)]
    prev = [0] * n
    for j in rng.sample(range(len(rem)), t):
        prev[j] = 1
    for j in rng.sample(range(len(add)), t):
        prev[len(rem) + j] = 1
    start = time.time()
    lines = ['seed=%d' % seed, 't=%d' % t, 'style=%d' % style,
             'mode=%d' % mode, 'batch=%d' % batch,
             'base=%d' % sum(levels), 'tasks=%d' % len(tasks),
             'phases=%d' % len(cuts)]
    def emit(extra=True):
        z = list(lines)
        if extra:
            z.append('last=' + ','.join(str(i) for i, v0 in enumerate(prev) if v0))
        open(out, 'w').write('\n'.join(z) + '\n')
    emit()
    reached = -1
    at = 0
    for ph, cut in enumerate(cuts):
        while at < cut:
            e, ri = tasks[at]
            levels[ri] = max(levels[ri], e)
            at += 1
        left = seconds - (time.time() - start)
        if left < 8:
            lines.append('p%d=NO_TIME' % ph)
            break
        model = cp_model.CpModel()
        v = [model.NewBoolVar('v%d' % i) for i in range(n)]
        model.Add(sum(v[:len(rem)]) == t)
        model.Add(sum(v[len(rem):]) == t)
        for ri, row in enumerate(rows3):
            add_row(model, v, rem, add, x0, row, row[0], t, 'a%d' % ri)
        for ri, lev in enumerate(levels):
            if lev:
                add_row(model, v, rem, add, x0, rows5[ri], 5 ** lev, t, 'b%d' % ri)
        if mode in (5, 6) and ph:
            model.Minimize(sum(v[i].Not() if prev[i] else v[i] for i in range(n)))
        for i, z in enumerate(prev):
            model.AddHint(v[i], z)
        solver = cp_model.CpSolver()
        budget = max(15.0, left / (len(cuts) - ph))
        solver.parameters.max_time_in_seconds = float(budget)
        solver.parameters.num_search_workers = 4
        solver.parameters.random_seed = seed + 1009 * ph
        solver.parameters.randomize_search = True
        solver.parameters.permute_variable_randomly = True
        solver.parameters.permute_presolve_constraint_order = True
        solver.parameters.repair_hint = True
        solver.parameters.hint_conflict_limit = 2000000
        solver.parameters.stop_after_first_solution = mode not in (5, 6)
        if mode in (1, 5):
            solver.parameters.search_branching = cp_model.PORTFOLIO_WITH_QUICK_RESTART_SEARCH
        elif mode == 2:
            solver.parameters.linearization_level = 0
            solver.parameters.search_branching = cp_model.PORTFOLIO_WITH_QUICK_RESTART_SEARCH
        elif mode == 3:
            solver.parameters.use_ls_only = True
            solver.parameters.use_feasibility_jump = True
        elif mode == 4:
            solver.parameters.search_branching = cp_model.RANDOMIZED_SEARCH
        elif mode == 6:
            solver.parameters.linearization_level = 0
            solver.parameters.search_branching = cp_model.PORTFOLIO_WITH_QUICK_RESTART_SEARCH
        elif mode != 0:
            raise RuntimeError(('mode', mode))
        t0 = time.time()
        status = solver.Solve(model)
        dt = time.time() - t0
        name = solver.StatusName(status)
        lines.append('p%d=%s,c=%d,d=%d,sec=%.2f,br=%d,cf=%d' %
                     (ph, name, cut, sum(levels), dt,
                      solver.NumBranches(), solver.NumConflicts()))
        emit()
        if status not in (cp_model.FEASIBLE, cp_model.OPTIMAL):
            break
        prev = [solver.Value(z) for z in v]
        reached = ph
        x = x0[:]
        for j, i in enumerate(rem):
            if prev[j]:
                x[i] = 0
        for j, i in enumerate(add):
            if prev[len(rem) + j]:
                x[i] = 1
        if sum(x) != 519:
            raise RuntimeError(('weight', sum(x)))
        verify(rows3, rows5, levels, x)
        emit()
        if cut == len(tasks):
            sel = [i for i, z in enumerate(x) if z]
            bb = bytearray((n + 7) // 8)
            for i in sel:
                bb[i >> 3] |= 1 << (i & 7)
            lines += ['FOUND', 'verified=1', 'k=%d' % len(sel),
                      'diff=%d' % (2 * t),
                      'bits=' + base64.b64encode(bb).decode(),
                      'indices=' + ','.join(map(str, sel))]
            emit(False)
            print('FOUND', t, time.time() - start)
            return 0
    lines += ['OPEN', 'reached=%d' % reached, 'sec=%.2f' % (time.time() - start)]
    emit()
    print('OPEN', reached)
    return 2

if __name__ == '__main__':
    if len(sys.argv) != 9:
        raise SystemExit(1)
    raise SystemExit(solve(sys.argv[1], int(sys.argv[2]), float(sys.argv[3]),
                           sys.argv[4], int(sys.argv[5]), int(sys.argv[6]),
                           int(sys.argv[7]), int(sys.argv[8])))
