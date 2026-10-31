#!/usr/bin/env python3
from __future__ import annotations
import argparse, gzip, hashlib, json
from pathlib import Path
from schema import APPROACH, read_json

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('run_dir')
    parser.add_argument('--require-accepted', action='store_true')
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    required = ['README.md','summary.json','minimized-certificates.json.gz','job-manifests.json','checksums.sha256']
    for name in required:
        if not (run_dir / name).is_file():
            raise SystemExit(f'missing archive file: {name}')
    summary = read_json(run_dir / 'summary.json')
    if summary.get('approach') != APPROACH or summary.get('task') != 'stage2_minimize_certificates':
        raise SystemExit('archive scope mismatch')
    if args.require_accepted and summary.get('accepted') is not True:
        raise SystemExit('run is not accepted')
    with gzip.open(run_dir / 'minimized-certificates.json.gz', 'rt', encoding='utf-8') as handle:
        payload = json.load(handle)
    records = payload.get('records', [])
    metrics = summary.get('metrics', {})
    if len(records) != int(metrics.get('classes_minimized', -1)):
        raise SystemExit('class count mismatch')
    if any(record.get('verified_exact') is not True for record in records):
        raise SystemExit('archive contains unverified minimized record')
    if len({record['canonical_support_id'] for record in records}) != len(records):
        raise SystemExit('duplicate canonical support id')
    expected = {}
    for line in (run_dir / 'checksums.sha256').read_text(encoding='utf-8').splitlines():
        digest, name = line.split('  ', 1)
        expected[name] = digest
    for name, digest in expected.items():
        if sha256(run_dir / name) != digest:
            raise SystemExit(f'checksum mismatch: {name}')
    print(json.dumps({'verified': True, 'run_dir': str(run_dir), 'summary': summary}, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
