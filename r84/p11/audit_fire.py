"""Audit a downloaded four-worker probe; never activates a production run."""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    for key in ('source', 'output', 'result'):
        p.add_argument('--'+key, type=Path, required=True)
    p.add_argument('--run-id', type=int, required=True)
    p.add_argument('--head-sha', required=True)
    a = p.parse_args()
    need(a.run_id > 0 and len(a.head_sha) == 40, 'run identity')
    sys.path.insert(0, str(a.source/'engine'))
    import paired_engine as engine
    root = a.output
    guard = json.loads((root/'guard/memory_result.json').read_text())
    multi = json.loads((root/'run/m.json').read_text())
    need(guard['status'] == 'completed' and guard['hard_limit_enforced'] is True and
         guard['child_returncode'] == 0 and not guard['last']['populated'], 'guard')
    need(not any(guard['last']['events'].get(k, 0) for k in ('oom', 'oom_kill', 'oom_group_kill')), 'oom')
    need(guard['peak_bytes'] < guard['limits']['warn_bytes'], 'memory headroom')
    need(multi['status'] == 'complete' and multi['peak_searches'] == 4 and
         multi['all_searches_overlap_seconds'] >= 30 and multi['cpu_capacity']['usable_cores'] >= 4,
         'four simultaneous workers')
    need(set(multi['workers']) == {'0', '1', '2', '3'}, 'worker count')
    audits = []
    seeds = set()
    for i in range(4):
        worker = root/'run'/f'{i:02d}'
        run = json.loads((worker/'run.json').read_text())
        row = run['branches']['2']; stats = row['kernel_stats']
        need(run['complete'] and run['order'] == [2] and run['seconds_per_branch'] == 120 and
             run['maxab'] == 6000 and run['vertices'] in (80000, 150000), 'worker contract')
        need(row['status'] == 'completed_budget' and row['returncode'] == 0 and
             row['seconds'] >= 119.95 and row['search_exercised'], 'full probe budget')
        need(stats['cap_hits'] == stats['single_fallbacks'] == 0 and
             stats['injection_generation'] == -1 and stats['block2_attempts'] > 0, 'operator')
        need(run['effective_seed16'] not in seeds, 'duplicate seed'); seeds.add(run['effective_seed16'])
        manifest, inst, initial, *_ = engine.admit(worker/'inputs', wide=True)
        need(manifest['population'] == 100 and sha(worker/'inputs/context.json') == run['source_context_sha256'], 'input identity')
        receipt = row['checkpoint']; path = worker/'recovery'/receipt['file']
        need(path.parent == worker/'recovery' and sha(path) == receipt['sha256'], 'checkpoint receipt')
        header, tours, costs = engine.read_text_checkpoint(path, inst, 100)
        engine.require_counter_progress((int(header[1]), int(header[7])), (int(initial[1]), int(initial[7])), 'parent')
        need(int(header[1]) == stats['generation'] and int(header[7]) == stats['children'] and
             header[2:4] == ['2', '2'], 'checkpoint telemetry')
        audits.append({'worker': i, 'routes': len(tours), 'checkpoint_sha256': sha(path),
                       'cpu_seconds': row['cpu_seconds'], 'context_sha256': run['source_context_sha256']})
    kit = Path(__file__).resolve().parent
    acceptance = {'status': 'PASS', 'seconds_per_worker': 120, 'completed_workers': 4,
                  'validated_final_routes': 400, 'hard_limit_enforced': True, 'oom_events': 0,
                  'empty_cgroup': True, 'peak_below_warning': True,
                  'four_search_overlap_seconds': multi['all_searches_overlap_seconds'],
                  'usable_cores': multi['cpu_capacity']['usable_cores']}
    result = {'run_id': a.run_id, 'attempt': 1, 'head_sha': a.head_sha, 'acceptance': acceptance,
              'runner_sha256': sha(kit/'run_experiment.py'), 'supervisor_sha256': sha(kit/'m.py'),
              'guard_report_sha256': sha(root/'guard/memory_result.json'),
              'multi_report_sha256': sha(root/'run/m.json'), 'workers': audits}
    # Caller must independently bind artifact identity and source revision to GitHub metadata.
    a.result.write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
