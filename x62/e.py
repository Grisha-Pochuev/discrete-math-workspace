#!/usr/bin/env python3
import random, sys, time
import b


def add_mod_rows(model, x, rows):
    for ri, (q, aa, target, meta) in enumerate(rows):
        nz = [(a, x[i]) for i, a in enumerate(aa) if a]
        total = sum(a for a, _ in nz)
        zmax = max(0, (total - target) // q)
        z = model.NewIntVar(0, zmax, 'z%d' % ri)
        model.Add(sum(a * v for a, v in nz) - q * z == target)


def q2_basis(split, n, order, seed):
    rows = []
    for q, aa, target, meta in split:
        if q != 2:
            continue
        mask = 0
        for i, a in enumerate(aa):
            if a & 1:
                mask |= 1 << i
        rows.append((mask, target & 1, meta))
    basis = b.gf2_rref(rows)
    out = [(p, mask, rhs) for p, (mask, rhs) in basis.items()]
    if len(out) != 62:
        raise RuntimeError(('q2-rank', len(out)))
    if order == 'a':
        out.sort(key=lambda z: z[1].bit_count())
    elif order == 'd':
        out.sort(key=lambda z: z[1].bit_count(), reverse=True)
    elif order == 'r':
        random.Random(seed ^ 0xE62A11).shuffle(out)
    else:
        raise RuntimeError(('order', order))
    return out


def add_xor_batch(model, x, rows):
    for p, mask, rhs in rows:
        lits = [x[i] for i in range(len(x)) if (mask >> i) & 1]
        if rhs:
            model.AddBoolXOr(lits)
        else:
            model.AddBoolXOr([lits[0].Not()] + lits[1:])


def configure(solver, seed, mode):
    from ortools.sat.python import cp_model
    solver.parameters.num_search_workers = 4
    solver.parameters.random_seed = int(seed)
    solver.parameters.randomize_search = True
    solver.parameters.permute_variable_randomly = True
    solver.parameters.permute_presolve_constraint_order = True
    solver.parameters.stop_after_first_solution = True
    solver.parameters.repair_hint = True
    solver.parameters.hint_conflict_limit = 200000
    if mode == 1:
        solver.parameters.search_branching = cp_model.PORTFOLIO_WITH_QUICK_RESTART_SEARCH
    elif mode == 2:
        solver.parameters.use_ls_only = True
        solver.parameters.use_feasibility_jump = True
    elif mode != 0:
        raise RuntimeError(('mode', mode))


def count_q2(rows, sol):
    return sum(1 for p, mask, rhs in rows
               if (sum(sol[i] for i in range(len(sol)) if (mask >> i) & 1) & 1) == rhs)


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


def solve(data_path, seed, seconds, out_path, order='a', mode=0, fix_count=0):
    from ortools.sat.python import cp_model
    P, F, maxe, targets, coords, split = b.build(data_path)
    n = len(P)
    modrows = [z for z in split if z[0] > 2]
    xb = q2_basis(split, n, order, seed)
    hint, hscore, hexact = b.xor_hint(coords, split, n, seed, steps=8000)
    rng = random.Random(seed ^ 0xE51A6E)
    fixed = sorted(rng.sample(range(n), min(max(0, fix_count), n)))
    start = time.time()
    lines = ['seed=%d' % seed, 'order=%s' % order, 'mode=%d' % mode,
             'fix=%d' % len(fixed), 'mod=%d' % len(modrows), 'q2=%d' % len(xb),
             'hint_k=%d' % sum(hint), 'hint_exact=%d' % hexact,
             'hint_score=%.6f' % hscore]

    prev = hint
    reached = -1
    last_name = 'UNKNOWN'
    # phase 0: all non-binary prime-power congruences, no extra XOR equations.
    # Then 4 cumulative batches of the remaining 62 independent q=2 equations.
    cuts = [0, 16, 31, 47, 62]
    deadlines = [0.25, 0.42, 0.60, 0.78, 1.0]
    for phase, (cut, frac) in enumerate(zip(cuts, deadlines)):
        elapsed = time.time() - start
        budget = seconds * frac - elapsed
        if budget < 3.0:
            lines.append('phase%d=NO_TIME' % phase)
            break
        model = cp_model.CpModel()
        x = [model.NewBoolVar('x%d' % i) for i in range(n)]
        k = model.NewIntVar(430, 600, 'k')
        model.Add(k == sum(x))
        add_mod_rows(model, x, modrows)
        if cut:
            add_xor_batch(model, x, xb[:cut])
        for i in fixed:
            model.Add(x[i] == hint[i])
        for i, v in enumerate(prev):
            model.AddHint(x[i], v)
        model.AddHint(k, sum(prev))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(budget)
        configure(solver, seed + 131 * phase, mode)
        t0 = time.time()
        status = solver.Solve(model)
        dt = time.time() - t0
        name = solver.StatusName(status)
        last_name = name
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            prev = [solver.Value(v) for v in x]
            reached = phase
            sat = count_q2(xb, prev)
            lines.append('phase%d=%s,xor=%d,sec=%.3f,k=%d,q2sat=%d,br=%d,cf=%d' %
                         (phase, name, cut, dt, sum(prev), sat,
                          solver.NumBranches(), solver.NumConflicts()))
            if cut == 62:
                sel = [i for i, v in enumerate(prev) if v]
                N = verify(P, F, maxe, targets, sel)
                lines += ['status=FOUND', 'verified=1', 'k=%d' % len(sel),
                          'indices=' + ','.join(map(str, sel)),
                          'factors=' + ','.join(str(P[i]) for i in sel),
                          'N=' + str(N)]
                with open(out_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(lines) + '\n')
                print('FOUND k=%d sec=%.3f' % (len(sel), time.time()-start))
                return 0
        else:
            lines.append('phase%d=%s,xor=%d,sec=%.3f,br=%d,cf=%d' %
                         (phase, name, cut, dt, solver.NumBranches(), solver.NumConflicts()))
            break
    lines += ['status=%s' % last_name, 'verified=0', 'reached=%d' % reached,
              'sec=%.6f' % (time.time() - start)]
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    print('END status=%s reached=%d sec=%.3f' % (last_name, reached, time.time()-start))
    return 2


if __name__ == '__main__':
    if len(sys.argv) != 8:
        print('usage: e.py DATA SEED SEC OUT ORDER MODE FIX', file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(solve(sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), sys.argv[4],
                           sys.argv[5], int(sys.argv[6]), int(sys.argv[7])))
