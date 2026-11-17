"""One guarded worker, fixed operators, complete immutable starting population."""
import argparse
import json
import math
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'engine'))
import paired_engine as engine


def supervise(binary, instance, directory, source, count, children, seed, ref, env, seconds, stop, grace=15):
    """No checkpoint parsing in the running-process watchdog."""
    started = time.monotonic(); cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
    proc = None; reason = None; terminate_at = None
    with (directory/'kernel.log').open('wb') as log:
        try:
            if stop[0]:
                return {'returncode': None, 'reason': 'cancelled_before_spawn', 'seconds': 0, 'cpu_seconds': 0}
            proc = subprocess.Popen([str(binary), str(instance), str(directory), str(count), str(children), str(seed),
                                     str(math.ceil(time.time()+seconds)), str(ref), str(source)],
                                    env=env, stdout=log, stderr=log, start_new_session=True)
            while proc.poll() is None:
                now = time.monotonic()
                if terminate_at is None and (stop[0] or now-started >= seconds+grace):
                    reason = 'cancelled' if stop[0] else 'deadline_overrun'
                    terminate_at = now
                    try:
                        os.killpg(proc.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                if terminate_at is not None and now-terminate_at >= grace:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                time.sleep(.1)
            used = resource.getrusage(resource.RUSAGE_CHILDREN)
            return {'returncode': proc.returncode, 'reason': reason, 'seconds': time.monotonic()-started,
                    'cpu_seconds': used.ru_utime+used.ru_stime-cpu.ru_utime-cpu.ru_stime}
        finally:
            if proc is not None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait(timeout=10)


def validate_production_admission(a, seconds, operators, deadline, now):
    if not isinstance(a, dict) or a.get('status') != 'APPROVED_ONE_SHOT':
        raise ValueError('reviewed production admission required')
    if not a.get('activation_epoch', 0) <= now < a.get('expiry_epoch', 0):
        raise ValueError('production admission time')
    review = a.get('production_review', {})
    if (review.get('status') != 'APPROVED' or review.get('seconds') != 19800 or
        review.get('operator') != 2 or review.get('vertices') != [80000] or
        review.get('protocol') != 'four-worker-window-diversity-v1' or review.get('workers_per_job') != 4 or
        type(review.get('fire_run')) is not int or review['fire_run'] <= 0 or
        review['fire_run'] == 43882564637 or review.get('fire_attempt') != 1 or
        seconds != 19800 or operators != '2'):
        raise ValueError('production review scope')
    fire = review.get('fire_acceptance', {})
    if (fire.get('status') != 'PASS' or fire.get('vertices_per_worker') != [80000]*4 or fire.get('input_modes') != ['b','c','d','e'] or fire.get('seconds_per_worker') != 120 or
        fire.get('completed_workers') != 4 or fire.get('validated_final_routes') != 400 or
        fire.get('hard_limit_enforced') is not True or fire.get('oom_events') != 0 or
        fire.get('empty_cgroup') is not True or fire.get('peak_below_warning') is not True or
        not isinstance(fire.get('four_search_overlap_seconds'), (float, int)) or
        not math.isfinite(fire['four_search_overlap_seconds']) or fire['four_search_overlap_seconds'] < 30 or
        not isinstance(fire.get('usable_cores'), (float, int)) or
        not math.isfinite(fire['usable_cores']) or fire['usable_cores'] < 4):
        raise ValueError('four-worker fire acceptance required')
    for k in ('fire_audit_sha256', 'independent_review_sha256'):
        value = review.get(k)
        if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('missing production evidence pin')
    if deadline is None or not math.isfinite(deadline) or deadline-now < 19800+1200:
        raise ValueError('production save budget')


def run(bundle, build, output, seconds, seed, operators='1,2', maxab=6000, job_deadline=None, tiny_test_only=False, production_admission=None):
    production = seconds == 19800
    if production:
        validate_production_admission(production_admission, seconds, operators, job_deadline, time.time())
    bundle, build, output = map(lambda p: Path(p).resolve(), (bundle, build, output))
    stages = [int(v) for v in operators.split(',')]
    if stages not in ([1], [2], [1,2]):
        raise ValueError('operators must be 1, 2 or 1,2')
    if not 0 <= seed < 2147483647 or not (1 <= seconds <= 9000 or seconds == 19800) or not 1 <= maxab <= 30000:
        raise ValueError('invalid budget/seed/cap')
    if tiny_test_only:
        files = list(bundle.iterdir())
        if len(files) > 12 or any(not f.is_file() or f.is_symlink() or f.stat().st_size > 10*1024**2 for f in files):
            raise ValueError('tiny input limit')
        guard = {'test_only': True}
    else:
        if job_deadline is None or not math.isfinite(job_deadline) or job_deadline-time.time() < len(stages)*(seconds+30)+600:
            raise ValueError('insufficient actual job budget, including preparation and upload')
        guard = engine.verify_guard()
    bm = json.loads((build/'build.json').read_text())
    required = ('experimental_wide','experimental_objective64','numeric_guards','verify_eax_invariants','object_cleanup_fixed','compact_storage')
    if not all(bm.get(k) is True for k in required) or engine.sha(build/'kernel') != bm['binary_sha256']:
        raise ValueError('requires checked compact/wide/objective64 build')
    m, inst, hdr, pop, values, base, ref = engine.admit(bundle, wide=True)
    if tiny_test_only:
        if inst.n > 256 or m['population'] > 8 or seconds > 3 or maxab > 256:
            raise ValueError('tiny execution limit')
    else:
        if inst.n != 80000 or (m['population'],m['children'],m['fixm']) != (100,30,200000):
            raise ValueError('unsupported production input dimensions')
        # Explicit first target step, not a claim of certified large-scale production.
        if inst.n == 150000 and ((seconds > 300 and not production) or len(stages) != 1):
            raise ValueError('150k package is limited to a single-operator pilot of at most 300 seconds')
    output.mkdir(parents=True, exist_ok=False)
    inputs = output/'inputs'; inputs.mkdir()
    for item in m['files'].values():
        shutil.copyfile(bundle/item['file'], inputs/item['file'])
    engine.atomic_json(inputs/'context.json', m)
    m, inst, hdr, pop, values, base, ref = engine.admit(inputs, wide=True)
    shutil.copyfile(build/'kernel', output/'kernel'); (output/'kernel').chmod(0o700)
    if engine.sha(output/'kernel') != bm['binary_sha256']:
        raise ValueError('copied executable mismatch')
    recovery = output/'recovery'; recovery.mkdir()
    ordered = engine.hashlib.sha256(b''.join(t.astype('<i8').tobytes() for t in pop)).hexdigest()
    context_hash = engine.sha(inputs/'context.json')
    manifest = {'schema': 1, 'protocol': 'fixed-operator-resume-v1', 'vertices': inst.n,
                'source_context_sha256': context_hash, 'ordered_population_sha256': ordered,
                'seed': seed, 'effective_seed16': seed & 65535, 'seconds_per_branch': seconds,
                'maxab': maxab, 'build': bm, 'guard': guard, 'branches': {},
                'initial_best_gap': min(values)-ref, 'initial_mean_gap': float(sum(values)/len(values)-ref),
                'initial_base_present': engine.edgekey(base) in {engine.edgekey(t) for t in pop},
                'injection': False, 'migration': False, 'restart': False, 'rng_state_restored': False,
                'global_improvement_verified': False, 'target_150k_production_certified': False}
    order = list(stages)
    if len(order) == 2 and seed % 2:
        order.reverse()
    manifest['order'] = order
    engine.atomic_json(output/'run.json', manifest)
    stop = [False]
    old = {s: signal.signal(s, lambda signum, frame: stop.__setitem__(0, True)) for s in (signal.SIGTERM,signal.SIGINT)}
    try:
        for stage in order:
            name = str(stage); row = {'status': 'not_started'}; manifest['branches'][name] = row
            if stop[0] or (not tiny_test_only and job_deadline-time.time() < seconds+330):
                row['status'] = 'not_started_budget_or_stop'
                engine.atomic_json(output/'run.json', manifest)
                continue
            directory = output/name; directory.mkdir()
            ih = list(hdr); ih[2] = ih[3] = str(stage)
            engine.write_checkpoint(directory/'input.txt', ih, pop, values)
            engine.snapshot(recovery, name, directory/'input.txt', inst, m['population'], stage, context_hash, ref, engine.edgekey(base))
            row.update(status='running', reserved_seconds=seconds, initial_generation=int(hdr[1]), initial_children=int(hdr[7]), input_sha256=engine.sha(directory/'input.txt'))
            engine.atomic_json(output/'run.json', manifest)
            env = engine.kernel_environment(stage, seconds, maxab, m['fixm'], inputs/m['files']['base']['file'])
            result = supervise(output/'kernel', inst.path, directory, directory/'input.txt', m['population'], m['children'], seed, ref, env, seconds, stop)
            row.update(result)
            try:
                ck = engine.snapshot(recovery, name, directory/'ck.txt', inst, m['population'], stage, context_hash, ref, engine.edgekey(base))
                stats = json.loads((directory/'kernel_stats.json').read_text())
                if ck['generation'] < int(hdr[1]) or ck['children'] < int(hdr[7]):
                    raise ValueError('counter regression')
                if stats['injection_generation'] != -1 or stats['single_fallbacks'] != 0 or (stage == 1 and stats['block2_attempts'] != 0):
                    raise ValueError('operator/injection contract violation')
                if any(stats[k] != ck[k] for k in ('generation','children','tag')):
                    raise ValueError('telemetry/checkpoint mismatch')
                exercised = ck['generation'] > int(hdr[1]) or ck['children'] > int(hdr[7]) or stats['block2_attempts'] > 0
                row.update(checkpoint=ck, kernel_stats=stats, search_exercised=exercised)
                complete = result['returncode'] == 0 and result['reason'] is None and not stop[0] and result['seconds'] >= seconds-.05 and ck['tag'] == 'deadline' and stats['cap_hits'] == 0 and exercised
                row['status'] = 'completed_budget' if complete else 'incomplete_or_failed'
            except (ValueError,OSError,KeyError) as exc:
                row.update(status='invalid_or_missing_checkpoint', error=str(exc))
            engine.atomic_json(output/'run.json', manifest)
        manifest['complete'] = all(manifest['branches'].get(str(s),{}).get('status') == 'completed_budget' for s in stages)
        engine.atomic_json(output/'run.json', manifest)
        return 0 if manifest['complete'] else 2
    finally:
        for s, handler in old.items():
            signal.signal(s, handler)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for k in ('bundle','build','output'): p.add_argument('--'+k, type=Path, required=True)
    for k in ('seconds','seed'): p.add_argument('--'+k, type=int, required=True)
    p.add_argument('--operators', default='1,2'); p.add_argument('--maxab', type=int, default=6000)
    p.add_argument('--job-deadline', type=float); p.add_argument('--tiny-test-only', action='store_true')
    return run(**vars(p.parse_args()))


if __name__ == '__main__':
    raise SystemExit(main())
