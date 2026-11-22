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


def expand_tour(tour, old_vertices, old_fixed, new_vertices, reference, pos):
    """Insert newly visible vertices along the unchanged outside reference paths."""
    old_n = len(old_vertices); new_n = len(new_vertices)
    new_pos = pos[new_vertices]
    inverse = np.full(len(reference), -1, dtype='i8'); inverse[new_vertices] = np.arange(new_n)
    fixed_starts = set(map(int, old_fixed[:, 0]))
    pieces = []
    for a, b in zip(tour, np.roll(tour, -1)):
        a, b = int(a), int(b)
        pieces.append(np.array([inverse[old_vertices[a]]], dtype='i8'))
        forward = a in fixed_starts and b == (a+1) % old_n
        reverse = b in fixed_starts and a == (b+1) % old_n
        if not (forward or reverse):
            continue
        lo = int(pos[old_vertices[a if forward else b]])
        hi = int(pos[old_vertices[b if forward else a]])
        first = int(np.searchsorted(new_pos, lo, side='right'))
        last = int(np.searchsorted(new_pos, hi, side='left'))
        mid = np.arange(first, last) if lo < hi else np.concatenate((np.arange(first, new_n), np.arange(last)))
        pieces.append(mid if forward else mid[::-1])
    result = np.concatenate(pieces)
    need(permutation(result, new_n), 'lift did not preserve one complete cycle')
    return result


def expand_region(bundle, coordinates, reference, output, size=150000):
    x, r = load_global(coordinates, reference)
    m, inst, hdr, pop, vals, base, ref, v, pos = bind_global(bundle, x, r)
    need(len(v) < size <= len(x), 'expanded region size')
    # Geometrical neighbourhood, ties resolved by global ID. Original region is kept in full.
    center = x[v].mean(axis=0); distance = ((x-center)**2).sum(axis=1)
    distance[v] = np.inf
    count = size-len(v); cutoff = np.partition(distance, count-1)[count-1]
    lower = np.flatnonzero(distance < cutoff); tied = np.flatnonzero(distance == cutoff)
    selected = np.concatenate((v, lower, tied[:count-len(lower)]))
    vv, fixed, _ = local_geometry(x, r, selected)
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp); write_instance(stage/'instance.bin', x[vv], fixed)
        np.save(stage/'vertices.npy', vv.astype('<i8'))
        (stage/'base.txt').write_text(f'{size} 0\n'+' '.join(map(str, np.arange(size)+1))+'\n')
        new = engine.Instance(stage/'instance.bin', m['fixm'], wide=True)
        new_ref = new.validate(np.arange(size))
        lifted = [expand_tour(t, v, inst.fixed, vv, r, pos) for t in pop]
        values = [new.validate(t) for t in lifted]
        need(np.array_equal(np.array(values)-new_ref, np.array(vals)-ref), 'lift changed full-route cost')
        hdr = list(hdr); hdr[8] = str(min(values))
        engine.write_checkpoint(stage/'checkpoint.txt', hdr, lifted, values)
        # Keep all generation/child history, but explicitly distinguish geometry transformation.
        meta = {k: m[k] for k in ('fixm','population','children','source_run','source_slot','global_binding')}
        meta['identity_evidence'] = {'kind': 'nested-region-transfer', 'source_context_sha256': engine.sha(Path(bundle)/'context.json'), 'old_size': len(v), 'new_size': size, 'all_old_vertices_preserved': True, 'ordered_full_routes_preserved': True, 'all_population_cost_gaps_equal': True, 'selection': 'nearest to old region centroid; global-ID tie break', 'native_rng_resume': False}
        meta['ordered_population_sha256'] = digest_array(np.asarray(lifted, dtype='<i8'))
        publish_bundle(stage, output, meta)
    return meta



