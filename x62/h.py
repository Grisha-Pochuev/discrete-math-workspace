#!/usr/bin/env python3
import math, random, sys, time
import b
from ortools.sat.python import cp_model


def xor_rows(coords, n):
    rr = b.gf2_rref(b.gf2_rows(coords, n))
    if len(rr) != 119:
        raise RuntimeError(('xor-rank', len(rr)))
    return [v for _, v in sorted(rr.items())]


def add_xors(model, x, rows):
    for mask, rhs in rows:
        lits = [x[i] for i in range(len(x)) if (mask >> i) & 1]
        if not lits:
            if rhs:
                model.AddBoolOr([])
        elif rhs:
            model.AddBoolXOr(lits)
        else:
            model.AddBoolXOr([lits[0].Not()] + lits[1:])


def row_bits(row, form):
    q = row[0]
    z = math.log2(q)
    if q % 2 == 0:
        z -= 1.0
    return max(0.0, z)


def grouped_rows(coords, split, seed, order, form):
    if form == 0:
        dd = {}
        for q, aa, target, meta in split:
            if q > 2:
                dd.setdefault(meta, []).append((q, aa, target, meta))
        groups = list(dd.values())
    elif form == 1:
        groups = [[row] for row in coords if row[0] > 2]
    else:
        raise RuntimeError(('form', form))
    rng = random.Random(seed ^ 62007)
    weight = lambda g: sum(row_bits(z, form) for z in g)
    if order == 0:
        groups.sort(key=lambda g: (weight(g), g[0][3]))
    elif order == 1:
        groups.sort(key=lambda g: (-weight(g), g[0][3]))
    elif order == 2:
        rng.shuffle(groups)
    elif order == 3:
        groups.sort(key=lambda g: (weight(g), g[0][3]))
        out = []
        while groups:
            out.append(groups.pop(0))
            if groups:
                out.append(groups.pop())
        groups = out
    else:
        raise RuntimeError(('order', order))
    return groups


def add_row(model, x, row, k, ri, enc):
    q, aa, target, _ = row
    if enc:
        model.AddModuloEquality(target, sum(a * x[i] for i, a in enumerate(aa) if a), q)
        return
    if k:
        vals = sorted(aa)
        lo = sum(vals[:k])
        hi = sum(vals[-k:])
    else:
        lo = 0
        hi = sum(aa)
    zlo = max(0, (lo - target + q - 1) // q)
    zhi = max(zlo, (hi - target) // q)
    z = model.NewIntVar(zlo, zhi, 'z%d' % ri)
    model.Add(sum(a * x[i] for i, a in enumerate(aa) if a) - q * z == target)


def verify(P, coords, split, sol):
    for m, aa, target, meta in coords:
        if sum(aa[i] for i in sol) % m != target:
            raise RuntimeError(('coord', meta))
    for q, aa, target, meta in split:
        if sum(aa[i] for i in sol) % q != target:
            raise RuntimeError(('split', q, meta))
    N = 1
    for i in sol:
        N *= P[i]
    for i in sol:
        p = P[i]
        if (N - 1) % (p - 1) or (N + 1) % (p + 1):
            raise RuntimeError(('direct', i, p))
    return N


def solve(path, seed, seconds, out_path, order, mode, form, chunk, k):
    P, _, _, _, coords, split = b.build(path)
    n = len(P)
    xb = xor_rows(coords, n)
    groups = grouped_rows(coords, split, seed, order, form)
    total_bits = sum(row_bits(z, form) for g in groups for z in g)
    cuts = [0]
    acc = 0.0
    mark = float(chunk)
    for i, g in enumerate(groups, 1):
        acc += sum(row_bits(z, form) for z in g)
        if acc + 1e-12 >= mark:
            cuts.append(i)
            mark += chunk
    if cuts[-1] != len(groups):
        cuts.append(len(groups))

    rng = random.Random(seed ^ 62026)
    if k:
        hs = set(rng.sample(range(n), k))
        prev = [int(i in hs) for i in range(n)]
    else:
        prev = [rng.getrandbits(1) for _ in range(n)]
    start = time.time()
    lines = [
        'seed=%d' % seed, 'order=%d' % order, 'mode=%d' % mode,
        'form=%d' % form, 'chunk=%d' % chunk, 'k=%d' % k,
        'xor=%d' % len(xb), 'groups=%d' % len(groups),
        'bits=%.6f' % total_bits, 'phases=%d' % len(cuts),
    ]
    reached = -1
    for ph, cut in enumerate(cuts):
        left = seconds - (time.time() - start)
        if left < 5:
            lines.append('p%d=NO_TIME' % ph)
            break
        budget = max(8.0, left / (len(cuts) - ph))
        model = cp_model.CpModel()
        x = [model.NewBoolVar('x%d' % i) for i in range(n)]
        if k:
            model.Add(sum(x) == k)
        add_xors(model, x, xb)
        ri = 0
        for group in groups[:cut]:
            for row in group:
                add_row(model, x, row, k, ri, mode in (7, 8))
                ri += 1
        for i, v in enumerate(prev):
            model.AddHint(x[i], v)

        if mode == 1 and ph:
            model.Minimize(sum(x[i].Not() if v else x[i] for i, v in enumerate(prev)))
        elif mode == 2 and ph:
            done_bits = sum(row_bits(z, form) for g in groups[:cut] for z in g)
            remaining = total_bits - done_bits
            nf = min(24, max(0, int((remaining - 80.0) / 8.0)))
            if nf:
                for i in rng.sample(range(n), nf):
                    model.Add(x[i] == prev[i])

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(budget)
        solver.parameters.num_search_workers = 4
        solver.parameters.random_seed = seed + 1009 * ph
        solver.parameters.randomize_search = True
        solver.parameters.permute_variable_randomly = True
        solver.parameters.permute_presolve_constraint_order = True
        solver.parameters.stop_after_first_solution = True
        solver.parameters.repair_hint = True
        solver.parameters.hint_conflict_limit = 500000
        if mode == 3:
            solver.parameters.search_branching = cp_model.PORTFOLIO_WITH_QUICK_RESTART_SEARCH
        elif mode == 4:
            solver.parameters.use_ls_only = True
            solver.parameters.use_feasibility_jump = True
        elif mode == 5:
            solver.parameters.linearization_level = 0
        elif mode == 6:
            solver.parameters.linearization_level = 0
            solver.parameters.cp_model_presolve = False
        elif mode == 8:
            solver.parameters.linearization_level = 0
        elif mode not in (0, 1, 2, 7):
            raise RuntimeError(('mode', mode))

        t0 = time.time()
        status = solver.Solve(model)
        dt = time.time() - t0
        name = solver.StatusName(status)
        lines.append('p%d=%s,g=%d,r=%d,sec=%.3f,br=%d,cf=%d' %
                     (ph, name, cut, ri, dt,
                      solver.NumBranches(), solver.NumConflicts()))
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            break
        prev = [solver.Value(v) for v in x]
        reached = ph
        if cut == len(groups):
            sol = [i for i, v in enumerate(prev) if v]
            N = verify(P, coords, split, sol)
            lines += [
                'status=FOUND', 'verified=1',
                'indices=' + ','.join(map(str, sol)),
                'factors=' + ','.join(str(P[i]) for i in sol),
                'N=' + str(N),
            ]
            open(out_path, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
            print('FOUND k=%d sec=%.3f' % (len(sol), time.time() - start))
            return 0
    lines += ['status=OPEN', 'verified=0', 'reached=%d' % reached,
              'sec=%.6f' % (time.time() - start)]
    open(out_path, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print('END reached=%d sec=%.3f' % (reached, time.time() - start))
    return 2


if __name__ == '__main__':
    if len(sys.argv) != 10:
        print('usage: h.py DATA SEED SEC OUT ORDER MODE FORM CHUNK K', file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(solve(sys.argv[1], int(sys.argv[2]), float(sys.argv[3]),
                           sys.argv[4], int(sys.argv[5]), int(sys.argv[6]),
                           int(sys.argv[7]), int(sys.argv[8]), int(sys.argv[9])))
