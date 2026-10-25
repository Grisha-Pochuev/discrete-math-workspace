#!/usr/bin/env python3
from __future__ import annotations
import argparse, gzip, hashlib, json, os
from pathlib import Path
from typing import Any
from schema import APPROACH, read_json, validate_spec

def atomic_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    os.replace(tmp, path)

def write_gzip_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    with gzip.open(tmp, 'wt', encoding='utf-8', compresslevel=9) as handle:
        json.dump(data, handle, sort_keys=True, separators=(',', ':'))
        handle.write('\n')
    os.replace(tmp, path)

def read_gzip_json(path: Path) -> Any:
    with gzip.open(path, 'rt', encoding='utf-8') as handle:
        return json.load(handle)

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--artifacts', required=True)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--run-id', type=int, required=True)
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--expected-jobs', type=int, required=True)
    parser.add_argument('--minimum-jobs', type=int, required=True)
    parser.add_argument('--spec', required=True)
    parser.add_argument('--rescue', action='store_true')
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    artifacts = Path(args.artifacts).resolve()
    spec = validate_spec(read_json(args.spec), require_ready=True)
    run_index = int(spec['run_index'])
    run_dir = repo / 'fourth-approach' / 'runs' / f'run-{run_index:03d}-{args.run_id}'
    if run_dir.exists():
        raise SystemExit(f'refusing to overwrite archive: {run_dir}')
    run_dir.mkdir(parents=True)

    manifests: list[dict[str, Any]] = []
    payloads: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for manifest_path in sorted(artifacts.rglob('manifest.json')):
        try:
            manifest = read_json(manifest_path)
            manifests.append(manifest)
            result_file = manifest.get('result_file')
            result_path = manifest_path.parent / str(result_file)
            if manifest.get('status') not in {'SUCCESS', 'BOUNDED_INCOMPLETE'}:
                errors.append(manifest)
            elif not result_file or not result_path.is_file():
                errors.append({**manifest, 'collector_error': 'missing result file'})
            else:
                payloads.append(read_gzip_json(result_path))
        except Exception as exc:
            errors.append({'path': str(manifest_path), 'error': f'{type(exc).__name__}: {exc}'})

    records: dict[str, dict[str, Any]] = {}
    total_classes_values: set[int] = set()
    assigned_total = 0
    attempts = 0
    for payload in payloads:
        if payload.get('task') != 'stage2_minimize_certificates':
            errors.append({'collector_error': 'wrong payload task'})
            continue
        total_classes_values.add(int(payload.get('total_canonical_classes', -1)))
        assigned_total += int(payload.get('assigned_classes', 0))
        attempts += int(payload.get('attempts', 0))
        for record in payload.get('records', []):
            class_id = str(record.get('canonical_support_id', ''))
            if not class_id:
                errors.append({'collector_error': 'record missing canonical_support_id'})
                continue
            previous = records.get(class_id)
            rank = (int(record['minimized_support_size']), int(record['minimized_nonzero_terms']), int(record['coefficient_height']))
            if previous is None:
                records[class_id] = record
            else:
                old_rank = (int(previous['minimized_support_size']), int(previous['minimized_nonzero_terms']), int(previous['coefficient_height']))
                if rank < old_rank:
                    records[class_id] = record

    completed_jobs = sum(1 for item in manifests if item.get('status') in {'SUCCESS', 'BOUNDED_INCOMPLETE'})
    total_classes = next(iter(total_classes_values)) if len(total_classes_values) == 1 else -1
    rejected = [record for record in records.values() if record.get('verified_exact') is not True]
    coverage_ok = total_classes >= 0 and len(records) == total_classes
    accepted = (
        completed_jobs >= args.minimum_jobs
        and not errors
        and not rejected
        and coverage_ok
        and len(manifests) <= args.expected_jobs
    )
    ordered = [records[key] for key in sorted(records)]
    metrics = {
        'total_canonical_classes': total_classes,
        'classes_minimized': len(ordered),
        'coverage_ok': coverage_ok,
        'completed_jobs': completed_jobs,
        'optimization_attempts': attempts,
        'classes_with_smaller_support': sum(1 for r in ordered if int(r['support_removed']) > 0),
        'classes_with_fewer_terms': sum(1 for r in ordered if int(r['terms_removed']) > 0),
        'support_variables_removed': sum(int(r['support_removed']) for r in ordered),
        'certificate_terms_removed': sum(int(r['terms_removed']) for r in ordered),
        'independently_reverified': sum(1 for r in ordered if r.get('verified_exact') is True),
        'rejected_certificates': len(rejected),
    }
    write_gzip_json(run_dir / 'minimized-certificates.json.gz', {
        'schema_version': 1,
        'task': spec['task'],
        'minimality_scope': 'greedy deletion plus exact rational re-solving; not a global minimum proof',
        'records': ordered,
    })
    atomic_json(run_dir / 'job-manifests.json', {'manifests': manifests, 'errors': errors})
    summary = {
        'schema_version': 1,
        'approach': APPROACH,
        'accepted': accepted,
        'smoke': bool(args.smoke),
        'rescue': bool(args.rescue),
        'run_id': args.run_id,
        'run_index': run_index,
        'task': spec['task'],
        'source_sha': args.source_sha,
        'expected_jobs': args.expected_jobs,
        'minimum_jobs': args.minimum_jobs,
        'artifact_directories_found': len(manifests),
        'completed_jobs': completed_jobs,
        'worker_error_count': len(errors),
        'metrics': metrics,
        'scientific_interpretation': 'The minimized exact certificates apply only to recorded support-restricted n=6,d=3 systems; they do not prove the full conjecture.',
        'next_decision': 'Manually inspect the minimized library before any deletion-contrast run.',
    }
    atomic_json(run_dir / 'summary.json', summary)
    (run_dir / 'README.md').write_text(
        f"# Fourth approach run {run_index:03d}\n\n"
        f"- GitHub Actions run: `{args.run_id}`\n"
        f"- Accepted: `{accepted}`\n"
        f"- Completed jobs: `{completed_jobs}/{args.expected_jobs}`\n"
        f"- Canonical classes minimized: `{len(ordered)}/{total_classes}`\n"
        f"- Support variables removed: `{metrics['support_variables_removed']}`\n"
        f"- Certificate terms removed: `{metrics['certificate_terms_removed']}`\n\n"
        "Minimality is deterministic greedy deletion with exact rational re-solving, not a proof of global minimality.\n",
        encoding='utf-8',
    )
    checksum_lines = []
    for path in sorted(run_dir.iterdir()):
        if path.is_file() and path.name != 'checksums.sha256':
            checksum_lines.append(f'{sha256(path)}  {path.name}')
    (run_dir / 'checksums.sha256').write_text('\n'.join(checksum_lines) + '\n', encoding='utf-8')

    if not args.smoke:
        control_path = repo / 'fourth-approach' / 'control.json'
        launch_path = repo / 'fourth-approach' / 'launch.json'
        control = read_json(control_path)
        control.update(
            tracking_enabled=False,
            completed_runs=int(control.get('completed_runs', 0)) + (1 if accepted else 0),
            last_run_id=args.run_id,
            last_run_index=run_index,
            last_run_accepted=accepted,
            next_run_index=3 if accepted else 2,
            next_task='stage3_deletion_contrasts' if accepted else spec['task'],
            recommended_next_action='manual_review_run_002_before_any_next_run' if accepted else 'inspect_run_002_failure',
            smoke_required=False,
        )
        atomic_json(control_path, control)
        launch = read_json(launch_path)
        launch['enabled'] = False
        launch['nonce'] = f'fourth-run-002-completed-{args.run_id}' if accepted else f'fourth-run-002-failed-{args.run_id}'
        atomic_json(launch_path, launch)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if accepted else 3

if __name__ == '__main__':
    raise SystemExit(main())
