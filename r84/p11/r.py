"""Recover a worker's verified population into a fresh explicit input bundle."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile


def recover(engine, worker, output, allow_unreceipted=False):
    worker, output = worker.resolve(), output.resolve()
    if output == worker or worker in output.parents or output.exists():
        raise ValueError('output must be new and outside worker')
    inputs = worker/'inputs'
    manifest, inst, start, _, _, _, _ = engine.admit(inputs, wide=True)
    context = engine.sha(inputs/'context.json')
    run = json.loads((worker/'run.json').read_text())
    if context != run['source_context_sha256']:
        raise ValueError('worker input context mismatch')
    candidates = []
    pointer = worker/'recovery'/'2.json'
    if allow_unreceipted:
        # After forced termination an atomic kernel file can be newer than the
        # last receipt. Its route data is independently checked below.
        candidates.append((worker/'2'/'ck.txt', None))
    if pointer.is_file():
        receipt = json.loads(pointer.read_text())
        for row in (receipt, receipt.get('previous', {})):
            digest = row.get('sha256')
            if digest and row.get('context_sha256') == context and row.get('file') == f'2-{digest}.txt':
                candidates.append((pointer.parent/row['file'], digest))
    for source, expected in candidates:
        try:
            digest = engine.sha(source)
            if expected and digest != expected:
                raise ValueError('recovery checksum mismatch')
            header, tours, costs = engine.read_text_checkpoint(source, inst, manifest['population'])
            engine.require_counter_progress((int(header[1]), int(header[7])),
                                            (int(start[1]), int(start[7])), 'parent')
            if header[2:4] != ['2', '2'] or engine.sha(source) != digest:
                raise ValueError('checkpoint identity changed')
            break
        except (ValueError, OSError):
            continue
    else:
        raise ValueError('no valid checkpoint; use the original explicitly pinned parent')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        stage = Path(tmp)/'bundle'
        stage.mkdir()
        for key, record in manifest['files'].items():
            if key != 'checkpoint':
                shutil.copyfile(inputs/record['file'], stage/record['file'])
        name = manifest['files']['checkpoint']['file']
        engine.write_checkpoint(stage/name, header, tours, costs)
        manifest['files']['checkpoint']['sha256'] = engine.sha(stage/name)
        manifest['checkpoint_format'] = 'text'
        manifest['recovered_source_sha256'] = digest
        manifest['rng_state_restored'] = False
        engine.atomic_json(stage/'context.json', manifest)
        engine.admit(stage, wide=True)
        if output.exists():
            raise FileExistsError(output)
        stage.rename(output)
    return {'source_sha256': digest, 'context_sha256': engine.sha(output/'context.json'),
            'generation': int(header[1]), 'children': int(header[7]), 'receipt_verified': expected is not None}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('source', 'worker', 'output'):
        p.add_argument('--'+key, type=Path, required=True)
    p.add_argument('--allow-unreceipted', action='store_true')
    a = p.parse_args()
    sys.path.insert(0, str(a.source.resolve()/'engine'))
    import paired_engine as engine
    print(json.dumps(recover(engine, a.worker, a.output, a.allow_unreceipted), indent=2))


if __name__ == '__main__':
    main()
