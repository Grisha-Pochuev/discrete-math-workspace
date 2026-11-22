#!/usr/bin/env python3
import math, random, sys, time
import b


def xor_add(model, x, coords, rref):
    if not rref:
        return b.add_xor_constraints(model, x, coords)
    basis = b.gf2_rref(b.gf2_rows(coords, len(x)))
    for p, (mask, rhs) in sorted(basis.items()):
        lits = [x[i] for i in range(len(x)) if (mask >> i) & 1]
        if rhs:
            model.AddBoolXOr(lits)
        else:
            model.AddBoolXOr([lits[0].Not()] + lits[1:])
    return len(basis)


def row_info(row):
    q = row[0]
    return math.log2(q) - (1.0 if q % 2 == 0 else 0.0)


def order_rows(rows, how, seed):
    rows = list(rows)
    if how == 'd':
        rows.sort(key=lambda z: (z[0], z[3]), reverse=True)
    elif how == 'a':
        rows.sort(key=lambda z: (z[0], z[3]))
    elif how == 'r':
        random.Random(seed ^ 0xC62A11).shuffle(rows)
    else:
        raise RuntimeError(('order', how))
    return rows


def stage_cuts(rows, stages=8):
    total = sum(row_info(z) for z in rows)
    cuts = []
    j = 0
    acc = 0.0
    for s in range(1, stages + 1):
        target = total * s / stages
        while j < len(rows) and acc < target:
            acc += row_info(rows[j])
            j += 1
        cuts.append((j, acc))
    cuts[-1] = (len(rows), total)
    return cuts, total


def add_rows(model, x, rows):
    for ri, (q, aa, target, meta) in enumerate(rows):
        nz = [(a, x[i]) for i, a in enumerate(aa) if a]
        total = sum(a for a, _ in nz)
        zmax = max(0, (total - target) // q)
        z = model.NewIntVar(0, zmax, 'z%d' % ri)
        model.Add(sum(a * v for a, v in nz) - q * z == target)


def count_all(rows, sol):
    return sum(1 for q, aa, target, _ in rows
               if sum(a * v for a, v in zip(aa, sol)) % q == target)


def verify(P, F, maxe, targets, sel):
    if len(sel) < 3 or len(sel) % 2 != 1:
        raise RuntimeError(('count-parity', len(sel)))
    N = 1
    for i in sel:
        N *= P[i]
    for i in sel:
        p = P[i]
        if (N - 1) % (p - 1) or (N + 1) % (p + 1):
            raise RuntimeError(('verify-local', i, p))
    for i in sel:
        for r, e in F[i].items():
            if N % (r ** e) != targets[(r, maxe[r])] % (r ** e):
                raise RuntimeError(('verify-global', i, r, e))
    return N


def solve(data_path, seed, seconds, out_path, order='d', rref=1, quick=0, fix_count=0):
    from ortools.sat.python import cp_model
    P, F, maxe, targets, coords, split = b.build(data_path)
    n = len(P)
    rows0 = [z for z in split if z[0] > 2]
    rows = order_rows(rows0, order, seed)
    cuts, total_info = stage_cuts(rows, 8)
    hint, hscore, hexact = b.xor_hint(coords, split, n, seed, steps=12000)
    prev = hint
    rng = random.Random(seed ^ 0x51A6E)
    fixed = sorted(rng.sample(range(n), min(max(0, fix_count), n)))
    start = time.time()
    lines = [
        'seed=%d' % seed, 'order=%s' % order, 'rref=%d' % int(bool(rref)),
        'quick=%d' % int(bool(quick)), 'fix=%d' % len(fixed),
        'hint_k=%d' % sum(hint), 'hint_exact=%d' % hexact,
        'hint_score=%.6f' % hscore, 'rows=%d' % len(rows),
        'info=%.6f' % total_info,
    ]
    deadlines = [0.05, 0.11, 0.18, 0.27, 0.38, 0.52, 0.70, 1.0]
    reached = 0
    last_name = 'UNKNOWN'
    for si, ((cut, inf), frac) in enumerate(zip(cuts, deadlines), 1):
        elapsed = time.time() - start
        budget = seconds * frac - elapsed
        if budget < 3.0:
            lines.append('stage%d=NO_TIME' % si)
            break
        model = cp_model.CpModel()
        x = [model.NewBoolVar('x%d' % i) for i in range(n)]
        k = model.NewIntVar(430, 600, 'k')
        model.Add(k == sum(x))
        xor_add(model, x, coords, bool(rref))
        add_rows(model, x, rows[:cut])
        for i in fixed:
            model.Add(x[i] == hint[i])
        for i, v in enumerate(prev):
            model.AddHint(x[i], v)
        model.AddHint(k, sum(prev))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(budget)
        solver.parameters.num_search_workers = 4
        solver.parameters.random_seed = seed + 101 * si
        solver.parameters.randomize_search = True
        solver.parameters.permute_variable_randomly = True
        solver.parameters.permute_presolve_constraint_order = True
        solver.parameters.stop_after_first_solution = True
        solver.parameters.repair_hint = True
        solver.parameters.hint_conflict_limit = 200000
        if quick:
            solver.parameters.search_branching = cp_model.PORTFOLIO_WITH_QUICK_RESTART_SEARCH
        t0 = time.time()
        status = solver.Solve(model)
        dt = time.time() - t0
        name = solver.StatusName(status)
        last_name = name
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            prev = [solver.Value(v) for v in x]
            sat = count_all(rows0, prev)
            reached = si
            lines.append('stage%d=%s,n=%d,info=%.3f,sec=%.3f,k=%d,sat=%d,br=%d,cf=%d' %
                         (si, name, cut, inf, dt, sum(prev), sat,
                          solver.NumBranches(), solver.NumConflicts()))
            if cut == len(rows):
                sel = [i for i, v in enumerate(prev) if v]
                N = verify(P, F, maxe, targets, sel)
                lines += ['status=FOUND', 'verified=1', 'k=%d' % len(sel),
                          'indices=' + ','.join(map(str, sel)),
                          'factors=' + ','.join(str(P[i]) for i in sel),
                          'N=' + str(N)]
                with open(out_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(lines) + '\n')
                print('FOUND stage=%d k=%d sec=%.3f' % (si, len(sel), time.time()-start))
                return 0
        else:
            lines.append('stage%d=%s,n=%d,info=%.3f,sec=%.3f,br=%d,cf=%d' %
                         (si, name, cut, inf, dt, solver.NumBranches(), solver.NumConflicts()))
            break
    lines += ['status=%s' % last_name, 'verified=0', 'reached=%d' % reached,
              'sec=%.6f' % (time.time() - start)]
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    print('END status=%s reached=%d sec=%.3f' % (last_name, reached, time.time()-start))
    return 2


if __name__ == '__main__':
    if len(sys.argv) != 9:
        print('usage: c.py DATA SEED SEC OUT ORDER RREF QUICK FIX', file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(solve(sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), sys.argv[4],
                           sys.argv[5], int(sys.argv[6]), int(sys.argv[7]), int(sys.argv[8])))
