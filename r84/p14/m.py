"""Run explicit Block2 assignments under one Linux memory envelope."""
import argparse
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

SOURCE_PINS = {
    'run_experiment.py': '3cc769666054c4b39032ebc0e0ed09732115a638c276f10937b6621eec3cc98c',
    'engine/vendor/memory_guard.py': 'cf99706925e3505890a3287ac159cec6b1f469d2d134657283c9d855a68c1956',
}
SEED_LIMIT = 2147483647
SAVE = 1200
STARTUP = 300
GRACE = 25
THREAD_ENV = dict.fromkeys(
    ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS',
     'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS'), '1')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def jobs(rows, count):
    require(isinstance(rows, list) and len(rows) == count, 'wrong assignment count')
    seeds = set()
    for row in rows:
        require(set(row) == {'bundle', 'seed', 'context_sha256'}, 'expected bundle, seed and context SHA-256')
        pin = row['context_sha256']
        require(isinstance(pin, str) and len(pin) == 64 and
                all(c in '0123456789abcdef' for c in pin), 'invalid context SHA-256')
        seed = row['seed']
        require(type(seed) is int and 1 <= seed <= SEED_LIMIT-2, 'invalid seed')
        # glibc srand treats 0 as 1; excluding both signed boundaries also
        # avoids equivalent initialization at the modulus.
        require(seed & 65535 not in seeds, 'duplicate effective low16 seed')
        seeds.add(seed & 65535)
        require(Path(row['bundle']).is_absolute(), 'bundle must be absolute')
    return seeds


def cpu_capacity(cgroup=None):
    logical = len(os.sched_getaffinity(0))
    quotas = []
    if cgroup:
        root = Path('/sys/fs/cgroup')
        for folder in (cgroup, *cgroup.parents):
            if folder != root and root not in folder.parents:
                break
            path = folder/'cpu.max'
            if path.exists():
                cap, period = path.read_text().split()
                if cap != 'max':
                    quotas.append(int(cap)/int(period))
    return {'affinity': logical, 'quota_cores': min(quotas, default=None),
            'quota_visibility': cgroup is not None,
            'usable_cores': min([logical, *quotas])}


def check_budget(deadline, seconds):
    require(math.isfinite(deadline) and deadline-time.time() >= seconds+SAVE+STARTUP,
            'insufficient wall time including startup and upload reserve')


def write_report(path, data):
    tmp = path.with_suffix('.tmp')
    with tmp.open('w') as stream:
        json.dump(data, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def send(pid, sig):
    try:
        os.kill(pid, sig)
    except ProcessLookupError:
        pass


def process_table():
    table = {}
    for entry in Path('/proc').iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            fields = dict(line.split(':', 1) for line in (entry/'status').read_text().splitlines()
                          if ':' in line)
            table[int(entry.name)] = (int(fields['PPid']),
                int(fields.get('VmRSS', '0 kB').split()[0])*1024,
                fields['Name'].strip() == 'kernel' and fields['State'].split()[0] != 'Z')
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    return table


def inspect(table, pids):
    rss, kernels = 0, 0
    children = {}
    for pid, (parent, _, _) in table.items():
        children.setdefault(parent, []).append(pid)
    pending = list(pids)
    while pending:
        pid = pending.pop()
        pending.extend(children.get(pid, []))
        _, resident, kernel = table.get(pid, (0, 0, False))
        rss += resident
        kernels += kernel
    return rss, kernels


def reap(proc):
    try:
        pid, status, usage = os.wait4(proc.pid, os.WNOHANG)
    except ChildProcessError:
        raise RuntimeError('worker disappeared before accounting') from None
    if not pid:
        return None
    proc.returncode = os.waitstatus_to_exitcode(status)
    return {'returncode': proc.returncode, 'cpu_seconds': usage.ru_utime+usage.ru_stime}


def clean_adopted():
    """Kill and reap private descendants after all worker handles have been reaped."""
    until = time.monotonic()+5
    cleaned = set()
    while children := [pid for pid, row in process_table().items() if row[0] == os.getpid()]:
        for pid in children:
            cleaned.add(pid)
            send(pid, signal.SIGKILL)
            try:
                os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                pass
        if time.monotonic() >= until:
            raise RuntimeError('descendants remain after forced cleanup')
        time.sleep(.02)
    return sorted(cleaned)


def supervise(commands, output, until, capacity, grace=GRACE):
    """Linux subreaper keeps ownership even when the kernel starts a new session."""
    require(ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) == 0,
            'cannot become child subreaper')
    signal_seen = []
    lost = set()
    old = {s: signal.signal(s, lambda sig, _: signal_seen.append(sig))
           for s in (signal.SIGTERM, signal.SIGINT)}
    start = time.monotonic()
    report = {'status': 'running', 'cpu_capacity': capacity, 'workers': {},
              'sampled_peak_rss_bytes': 0, 'peak_searches': 0, 'all_searches_overlap_seconds': 0.0}
    active = {}
    terminating = None
    last_sample = start
    previous_kernels = 0
    try:
        write_report(output/'m.json', report)
        for idx, command in enumerate(commands):
            if signal_seen:
                break
            with (output/f'{idx:02d}.log').open('xb') as log:
                proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                        env={**os.environ, **THREAD_ENV}, start_new_session=True)
            active[idx] = proc
            report['workers'][str(idx)] = {'pid': proc.pid, 'started_seconds': time.monotonic()-start}
        while active:
            now = time.monotonic()
            if terminating is None and (signal_seen or now >= until):
                report['reason'] = 'signal' if signal_seen else 'deadline'
                terminating = now
                for proc in active.values():
                    send(proc.pid, signal.SIGTERM)
            table = process_table()
            owned = {proc.pid for proc in active.values()}
            for pid, row in table.items():
                if row[0] == os.getpid() and pid not in owned:
                    lost.add(pid)
                    send(pid, signal.SIGKILL)
                    try:
                        os.waitpid(pid, os.WNOHANG)
                    except ChildProcessError:
                        pass
            rss, kernels = inspect(table, [os.getpid()])
            report['sampled_peak_rss_bytes'] = max(rss, report['sampled_peak_rss_bytes'])
            report['peak_searches'] = max(kernels, report['peak_searches'])
            if kernels == previous_kernels == len(commands):
                report['all_searches_overlap_seconds'] += now-last_sample
            last_sample, previous_kernels = now, kernels
            for idx, proc in list(active.items()):
                if terminating is not None and now >= terminating+grace:
                    send(proc.pid, signal.SIGKILL)
                result = reap(proc)
                if result is not None:
                    result['finished_seconds'] = time.monotonic()-start
                    report['workers'][str(idx)].update(result)
                    del active[idx]
            if active:
                time.sleep(.1)
    finally:
        try:
            for proc in active.values():
                send(proc.pid, signal.SIGKILL)
            for idx, proc in active.items():
                report['workers'][str(idx)]['returncode'] = proc.wait(timeout=5)
            report['adopted_cleaned'] = sorted(lost.union(clean_adopted()))
            report['wall_seconds'] = time.monotonic()-start
            report['cpu_seconds'] = sum(row.get('cpu_seconds', 0) for row in report['workers'].values())
            complete = (not active and not signal_seen and len(report['workers']) == len(commands)
                        and terminating is None and not report['adopted_cleaned']
                        and all(row.get('returncode') == 0 for row in report['workers'].values()))
            report['status'] = 'complete' if complete else 'incomplete'
            write_report(output/'m.json', report)
        finally:
            for sig, handler in old.items():
                signal.signal(sig, handler)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('source', 'build', 'assignments', 'output'):
        p.add_argument('--'+key, type=Path, required=True)
    p.add_argument('--deadline', type=float, required=True)
    p.add_argument('--seconds', type=int, required=True)
    p.add_argument('--index', type=int, required=True)
    p.add_argument('--admission', type=Path)
    a = p.parse_args()
    source, output = a.source.resolve(), a.output.resolve()
    for name, digest in SOURCE_PINS.items():
        require(hashlib.sha256((source/name).read_bytes()).hexdigest() == digest, f'source pin: {name}')
    sys.path.insert(0, str(source))
    import run_experiment as runner

    rows = json.loads(a.assignments.read_text())
    require(len(rows) == 20 and 0 <= a.index < 20, 'expected 20 job assignments')
    jobs([entry for row in rows for entry in row], 80)
    for row in rows:
        jobs(row, 4)
    check_budget(a.deadline, a.seconds)
    require(1 <= a.seconds <= 9000 or a.seconds == 19800, 'unsupported duration')
    require((a.seconds == 19800) == (a.admission is not None), 'review file required only for long path')
    guard = runner.engine.verify_guard()
    capacity = cpu_capacity(Path(guard['path']))
    require(capacity['usable_cores'] >= 4, f'fewer than four available cores: {capacity}')
    if a.admission:
        admission = json.loads(a.admission.read_text())
        require(admission.get('assignments_sha256') == hashlib.sha256(a.assignments.read_bytes()).hexdigest(),
                'production assignments checksum')
        evidence_path = a.admission.parent/'fire_evidence.json'
        evidence_bytes = evidence_path.read_bytes()
        review = admission.get('production_review', {})
        require(hashlib.sha256(evidence_bytes).hexdigest() == review.get('fire_audit_sha256'),
                'fire evidence checksum')
        evidence = json.loads(evidence_bytes)
        require(evidence.get('run_id') == review.get('fire_run') and
                evidence.get('attempt') == review.get('fire_attempt') and
                evidence.get('acceptance') == review.get('fire_acceptance'), 'fire evidence identity')
        require(evidence.get('runner_sha256') == SOURCE_PINS['run_experiment.py'] and
                evidence.get('supervisor_sha256') == hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'fire tested different source version')
        runner.validate_production_admission(admission, a.seconds, '2', a.deadline, time.time())
    selected = rows[a.index]
    for row in selected:
        bundle = Path(row['bundle']).resolve(strict=True)
        require(bundle != output and bundle not in output.parents and output not in bundle.parents,
                'output must be separate from parent bundle')
        require((bundle/'context.json').is_file(), 'missing explicit parent manifest')
        context = json.loads((bundle/'context.json').read_text())
        require(runner.engine.sha(bundle/'context.json') == row['context_sha256'], 'parent context checksum')
        name = context['files']['instance']['file']
        require(Path(name).name == name and name not in ('', '.', '..'), 'unsafe instance name')
        inst = bundle/name
        with inst.open('rb') as stream:
            vertices = int.from_bytes(stream.read(4), 'little')
        require(vertices == 80000, 'parent dimensions')
        require(vertices != 150000 or a.seconds <= 300 or a.seconds == 19800,
                '150k accepts only short pilot or reviewed long path')
    output.mkdir(parents=True)
    write_report(output/'assignments.json', {'index': a.index, 'jobs': selected,
                                             'seconds': a.seconds, 'guard': guard})
    commands = []
    for idx, row in enumerate(selected):
        args = [str(source), row['bundle'], str(a.build.resolve()), str(output/f'{idx:02d}'),
                str(a.seconds), str(row['seed']), str(a.deadline),
                str(a.admission.resolve()) if a.admission else '']
        commands.append([sys.executable, str(Path(__file__).with_name('w.py')), *args])
    remaining = a.deadline-time.time()-SAVE
    report = supervise(commands, output, time.monotonic()+remaining-GRACE, capacity)
    return 0 if report['status'] == 'complete' else 2


if __name__ == '__main__':
    raise SystemExit(main())
