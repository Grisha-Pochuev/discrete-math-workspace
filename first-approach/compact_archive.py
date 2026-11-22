#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil

MAX_PUBLISH_BLOB = 95 * 1024 * 1024
FORMAT_VERSION = 2


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def gzip_deterministic(source: Path, target: Path) -> None:
    temporary = target.with_suffix(target.suffix + '.tmp')
    with source.open('rb') as src, temporary.open('wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, compresslevel=9, mtime=0) as dst:
            shutil.copyfileobj(src, dst, length=1024 * 1024)
    temporary.replace(target)
    source.unlink()


def patch_verifier(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    text = text.replace('import hashlib\n', 'import gzip\nimport hashlib\n', 1)
    old = '''summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))\nsource_document = json.loads((root / "source_tasks.json").read_text(encoding="utf-8"))\nsource_tasks = source_document["tasks"]\n'''
    new = '''def load_json_payload(name: str):\n    plain = root / name\n    compressed = root / f"{name}.gz"\n    if plain.exists():\n        return json.loads(plain.read_text(encoding="utf-8"))\n    with gzip.open(compressed, "rt", encoding="utf-8") as source:\n        return json.load(source)\n\nsummary = load_json_payload("summary.json")\nsource_document = load_json_payload("source_tasks.json")\nsource_tasks = source_document["tasks"]\n'''
    if old not in text:
        raise RuntimeError('generated verifier source-task loader did not match expected template')
    text = text.replace(old, new, 1)
    old_tail = 'print("PASS: exact source coverage, 20 ZIP checksums, exact support exclusions, zero swap")\n'
    new_tail = '''next_document = load_json_payload("next_tasks.json")\nnext_tasks = next_document["tasks"]\nnext_names = [\n    f"{item['stage']}-o{int(item['orbit'])}-l{int(item['limit'])}-s{int(item['shard']):05d}-of-{int(item['shards'])}"\n    for item in next_tasks\n]\nassert next_document["parent_run"] == summary["run_id"]\nassert next_document["stage"] == summary["next_frontier"]["stage"]\nassert len(next_names) == len(set(next_names)) == summary["next_frontier"]["tasks"]\n\narchive_checksum_lines = (root / "archive-checksums.sha256").read_text(encoding="utf-8").splitlines()\nfor line in archive_checksum_lines:\n    digest, relative = line.split(maxsplit=1)\n    payload = root / relative\n    assert hashlib.sha256(payload.read_bytes()).hexdigest() == digest\n\nassert summary["archive_format_version"] == 2\nprint("PASS: exact source coverage, 20 ZIP checksums, exact support exclusions, zero swap, compressed frontier integrity")\n'''
    if old_tail not in text:
        raise RuntimeError('generated verifier tail did not match expected template')
    path.write_text(text.replace(old_tail, new_tail, 1), encoding='utf-8')


def compact_archive(root: Path) -> None:
    required = [
        root / 'source_tasks.json',
        root / 'next_tasks.json',
        root / 'records.jsonl',
        root / 'summary.json',
        root / 'README.md',
        root / 'verify.py',
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f'missing archive files: {missing}')

    summary_path = root / 'summary.json'
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    removed_counts = {
        'incomplete_task_names': len(summary.pop('incomplete_task_names', [])),
        'unstarted_task_names': len(summary.pop('unstarted_task_names', [])),
    }
    summary['archive_format_version'] = FORMAT_VERSION
    summary['omitted_redundant_name_lists'] = removed_counts
    summary['payload_encoding'] = {
        'source_tasks': 'source_tasks.json.gz',
        'next_tasks': 'next_tasks.json.gz',
        'records': 'records.jsonl.gz',
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n', encoding='utf-8')

    patch_verifier(root / 'verify.py')

    readme = (root / 'README.md').read_text(encoding='utf-8')
    readme = readme.replace('`next_tasks.json`', '`next_tasks.json.gz`')
    readme += '''\n## Archive format\n\nLarge exact task queues and the record stream are stored as deterministic gzip files. Use `gzip -cd` or Python's `gzip` module. The verifier checks their integrity and the exact successor-task count.\n'''
    (root / 'README.md').write_text(readme, encoding='utf-8')

    for name in ('source_tasks.json', 'next_tasks.json', 'records.jsonl'):
        gzip_deterministic(root / name, root / f'{name}.gz')

    checksum_targets = [
        root / 'source_tasks.json.gz',
        root / 'next_tasks.json.gz',
        root / 'records.jsonl.gz',
        root / 'summary.json',
        root / 'README.md',
        root / 'verify.py',
    ]
    (root / 'archive-checksums.sha256').write_text(
        ''.join(f'{sha256(path)}  {path.relative_to(root).as_posix()}\n' for path in checksum_targets),
        encoding='utf-8',
    )

    oversized = [path for path in root.rglob('*') if path.is_file() and path.stat().st_size >= MAX_PUBLISH_BLOB]
    if oversized:
        details = [(path.relative_to(root).as_posix(), path.stat().st_size) for path in oversized]
        raise RuntimeError(f'archive still contains GitHub-unsafe blobs: {details}')

    sizes = sorted(
        ((path.stat().st_size, path.relative_to(root).as_posix()) for path in root.rglob('*') if path.is_file()),
        reverse=True,
    )
    print(json.dumps({'archive_format_version': FORMAT_VERSION, 'largest_files': sizes[:10]}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('archive', type=Path)
    args = parser.parse_args()
    compact_archive(args.archive.resolve())


if __name__ == '__main__':
    main()
