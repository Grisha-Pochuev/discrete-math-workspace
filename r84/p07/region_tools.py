"""Exact population transfer between nested regions; no search or network."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

import numpy as np
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'engine'))
import paired_engine as engine


def need(ok, message):
    if not ok:
        raise ValueError(message)


def digest_array(a):
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def permutation(a, n):
    return a.shape == (n,) and a.dtype.kind in 'iu' and np.array_equal(np.sort(a), np.arange(n))


def metric(x, tour):
    d = x[tour] - x[np.roll(tour, -1)]
    return int(np.floor(np.sqrt((d*d).sum(axis=1)) + .5).astype('i8').sum())


def load_global(coordinates, reference):
    def read(path, integer=False):
        if Path(path).suffix == '.npy':
            return np.load(path, allow_pickle=False)
        with gzip.open(path, 'rt') as f:
            return np.loadtxt(f, dtype='i8' if integer else 'f8') - (1 if integer else 0)
    x, r = read(coordinates), read(reference, True)
    need(x.ndim == 2 and x.shape[1] == 3 and np.isfinite(x).all(), 'global coordinates')
    need(permutation(r, len(x)), 'global reference must be a zero-based permutation in NPY')
    return x, r


def apply_edges(reference, removed, added):
    n = len(reference)
    adjacency = np.empty((n, 2), dtype='i8')
    adjacency[reference, 0] = np.roll(reference, 1)
    adjacency[reference, 1] = np.roll(reference, -1)
    for u, v in np.asarray(removed, dtype='i8'):
        need(0 <= u < n and 0 <= v < n and u != v, 'edge range')
        for a, b in ((u, v), (v, u)):
            hit = np.flatnonzero(adjacency[a] == b)
            need(len(hit) == 1, 'removed edge missing or duplicate')
            adjacency[a, hit[0]] = -1
    for u, v in np.asarray(added, dtype='i8'):
        need(0 <= u < n and 0 <= v < n and u != v, 'edge range')
        for a, b in ((u, v), (v, u)):
            free = np.flatnonzero(adjacency[a] == -1)
            need(len(free) and b not in adjacency[a], 'invalid added edge')
            adjacency[a, free[0]] = b
    need(np.all(adjacency >= 0), 'unfinished edge replacement')
    result = np.empty(n, dtype='i8'); seen = np.zeros(n, dtype=bool)
    cur = int(reference[0]); prev = int(adjacency[cur, 0])
    for j in range(n):
        need(not seen[cur], 'global subtour')
        seen[cur] = True; result[j] = cur
        a, b = adjacency[cur]
        prev, cur = cur, int(b if a == prev else a)
    need(cur == result[0], 'global route not closed')
    return result


def local_geometry(x, reference, ids):
    n = len(reference); ids = np.asarray(ids, dtype='i8')
    need(ids.ndim == 1 and len(ids) >= 51 and ids.min() >= 0 and ids.max() < n and len(np.unique(ids)) == len(ids), 'region IDs')
    pos = np.empty(n, dtype='i8'); pos[reference] = np.arange(n)
    vertices = ids[np.argsort(pos[ids], kind='stable')]
    pc = pos[vertices]; m = len(vertices)
    fi = np.flatnonzero((np.roll(pc, -1) - pc) % n != 1)
    fixed = np.stack((fi, (fi+1) % m), axis=1).astype('<i4')
    return vertices, fixed, pos


def write_instance(path, xyz, fixed):
    n = len(xyz); k = 50
    # Freeze actual resulting NN bytes. Never use regenerated NN to claim native identity.
    _, neighbors = cKDTree(xyz).query(xyz, k=k+1, workers=1)
    nn = np.empty((n, k), dtype='<i4')
    for i in range(n):
        nn[i] = neighbors[i][neighbors[i] != i][:k]
    with Path(path).open('wb') as f:
        np.array([n, len(fixed), k], dtype='<i4').tofile(f)
        np.asarray(xyz, dtype='<f8').tofile(f); fixed.tofile(f); nn.tofile(f)
    return nn


def publish_bundle(stage, output, meta):
    names = {'instance': 'instance.bin', 'vertices': 'vertices.npy', 'base': 'base.txt', 'checkpoint': 'checkpoint.txt'}
    meta.update(schema=1, files={k: {'file': v, 'sha256': engine.sha(stage/v)} for k, v in names.items()}, checkpoint_format='text')
    engine.atomic_json(stage/'context.json', meta)
    engine.admit(stage, wide=True)
    need(not Path(output).exists(), 'output already exists')
    shutil.copytree(stage, output)


def bind_global(bundle, x, r):
    m, inst, hdr, pop, vals, base, ref = engine.admit(bundle, wide=True)
    v = np.load(Path(bundle)/m['files']['vertices']['file'], allow_pickle=False)
    need(v.max() < len(x), 'global ID outside coordinates')
    vv, fixed, pos = local_geometry(x, r, v)
    need(np.array_equal(v, vv) and np.array_equal(fixed, inst.fixed), 'global boundary/reference mismatch')
    need(np.array_equal(x[v], inst.xyz) and np.array_equal(base, np.arange(len(v))), 'global coordinates/local reference mismatch')
    proof = m.get('global_binding', {})
    need(proof.get('coordinates_array_sha256') == digest_array(x.astype('<f8')) and proof.get('reference_array_sha256') == digest_array(r.astype('<i8')), 'full reference or coordinates changed')
    return m, inst, hdr, pop, vals, base, ref, v, pos


def directory_root(folder):
    records = []
    for p in sorted(Path(folder).iterdir(), key=lambda f: f.name):
        need(p.is_file() and not p.is_symlink() and p.stat().st_size <= 128*1024**2, 'parent contains non-regular or excessive file')
        records.append([p.name, p.stat().st_size, engine.sha(p)])
    need(len(records) <= 128 and sum(r[1] for r in records) <= 512*1024**2, 'parent size')
    payload = json.dumps(records, ensure_ascii=True, separators=(',', ':')).encode()
    return hashlib.sha256(b'GAIA_PARENT_DIRECTORY_V1\0'+payload).hexdigest()


def import_parent(parent, geometry, coordinates, reference, slot, island, expected_root, output):
    """Reconstruct an explicitly labelled current anchor from an audited artifact."""
    parent = Path(parent)
    need(directory_root(parent) == expected_root, 'parent directory digest mismatch')
    s = json.loads((parent/'s.json').read_text())
    completion = json.loads((parent/'completion.json').read_text())
    exits = json.loads((parent/'child_exits.json').read_text())
    need(s['s'] == slot and 0 <= island < 4 and s['harvest_allowed'] is True and not s['runtime_errors'], 'parent incomplete')
    need(completion['status'] == 'COMPLETE_PENDING_INDEPENDENT_AUDIT' and exits == s['child_exits'] == completion['child_exits'], 'parent completion mismatch')
    need(len(exits) == 4 and {e['k'] for e in exits} == set(range(4)) and all(e['rc'] == 0 and e['trial'] == 0 for e in exits), 'parent child exit')
    x, r = load_global(coordinates, reference)
    with np.load(geometry, allow_pickle=False) as g:
        need('o' in g and 'i' in g and 'rc' not in g, 'requires explicit indexed geometry')
        if 'dr' in g:
            r = apply_edges(r, g['dr'], g['da'])
        offsets = g['o'].astype('i8'); ri = slot % (len(offsets)-1)
        ids = g['i'][offsets[ri]:offsets[ri+1]].astype('i8')
    need(s['ri'] == ri and len(ids) == 80000, '80k region identity')
    v, fixed, _ = local_geometry(x, r, ids)
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        write_instance(stage/'instance.bin', x[v], fixed)
        np.save(stage/'vertices.npy', v.astype('<i8'))
        base = np.arange(len(v), dtype='i8')
        (stage/'base.txt').write_text(f'{len(v)} 0\n'+' '.join(map(str, base+1))+'\n')
        inst = engine.Instance(stage/'instance.bin', 200000, wide=True)
        hdr, pop, vals = engine.import_legacy(parent/f'c{island}.bin', inst, 100, 300*1024**2)
        need(hdr[-1] == 'deadline', 'only completed parent checkpoint')
        ref = inst.validate(base); gaps = np.array(vals, dtype='i8') - ref
        row = next(a for a in s['isl'] if a['k'] == island)
        need(row['np'] == 100 and row['g'] == int(hdr[1]) and row['st'] == int(hdr[2]) and row['tag'] == hdr[-1], 'parent header mismatch')
        need(row['b'] == int(gaps.min()) and abs(row['a']-float(gaps.mean())) < 1e-6 and np.array_equal(row['q'], np.sort(gaps)[:10]), 'parent reported costs disagree with reconstruction')
        engine.write_checkpoint(stage/'checkpoint.txt', hdr, pop, vals)
        meta = {'fixm': 200000, 'population': 100, 'children': 30,
                'source_run': s['runtime_identity']['GITHUB_RUN_ID'], 'source_slot': f'o{slot}/k{island}',
                'identity_evidence': {'kind': 'reconstructed-validated-anchor', 'parent_root': expected_root, 'geometry_sha256': engine.sha(geometry), 'native_nn_identity_claimed': False, 'parent_summary_metrics_checked': True},
                'global_binding': {'coordinates_array_sha256': digest_array(x.astype('<f8')), 'reference_array_sha256': digest_array(r.astype('<i8')), 'reference_cost': metric(x, r)},
                'ordered_population_sha256': digest_array(np.asarray(pop, dtype='<i8'))}
        need(directory_root(parent) == expected_root, 'parent changed during conversion')
        publish_bundle(stage, output, meta)
    # Full inputs stay private; only local bundle is selected for public export.
    np.save(Path(output).parent/(Path(output).name+'_full_reference.npy'), r)
    return meta

