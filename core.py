#!/usr/bin/env python3
"""Generic finite polynomial-system utilities."""

from __future__ import annotations

import argparse
import itertools
import time

import numpy as np
from scipy.optimize import least_squares
from scipy.sparse import csr_matrix


N = 6
D = 3


def perfect_matchings(vertices: tuple[int, ...]):
    if not vertices:
        yield ()
        return
    i = vertices[0]
    for p in range(1, len(vertices)):
        j = vertices[p]
        rest = vertices[1:p] + vertices[p + 1 :]
        for tail in perfect_matchings(rest):
            yield ((i, j),) + tail


MATCHINGS = tuple(perfect_matchings(tuple(range(N))))
COLOURINGS = np.asarray(tuple(itertools.product(range(D), repeat=N)), dtype=np.int8)
EDGES = tuple((i, j) for i in range(N) for j in range(i + 1, N))
EDGE_POS = {e: k for k, e in enumerate(EDGES)}
NV = len(EDGES) * D * D
NC = len(COLOURINGS)


def var_index(i: int, j: int, a: int, b: int) -> int:
    if i > j:
        i, j, a, b = j, i, b, a
    return (EDGE_POS[(i, j)] * D + a) * D + b


TERM_VARS = np.empty((NC, len(MATCHINGS), N // 2), dtype=np.int16)
for ci, colours in enumerate(COLOURINGS):
    for mi, matching in enumerate(MATCHINGS):
        TERM_VARS[ci, mi] = [var_index(i, j, int(colours[i]), int(colours[j])) for i, j in matching]

TARGET = np.zeros(NC, dtype=np.complex128)
for a in range(D):
    idx = sum(a * D ** (N - 1 - i) for i in range(N))
    TARGET[idx] = 1.0


def unpack(y: np.ndarray) -> np.ndarray:
    return y[:NV] + 1j * y[NV:]


def amplitudes(x: np.ndarray) -> np.ndarray:
    selected = x[TERM_VARS]
    return np.prod(selected, axis=2).sum(axis=1)


def residual(y: np.ndarray) -> np.ndarray:
    r = amplitudes(unpack(y)) - TARGET
    return np.concatenate((r.real, r.imag))


def jacobian(y: np.ndarray) -> csr_matrix:
    x = unpack(y)
    deriv = np.zeros((NC, NV), dtype=np.complex128)
    for k in range(N // 2):
        other = [q for q in range(N // 2) if q != k]
        vals = np.prod(x[TERM_VARS[:, :, other]], axis=2)
        rows = np.repeat(np.arange(NC), len(MATCHINGS))
        cols = TERM_VARS[:, :, k].ravel()
        np.add.at(deriv, (rows, cols), vals.ravel())
    rr, cc = np.nonzero(deriv)
    z = deriv[rr, cc]
    rows = np.concatenate((rr, rr, rr + NC, rr + NC))
    cols = np.concatenate((cc, cc + NV, cc, cc + NV))
    data = np.concatenate((z.real, -z.imag, z.imag, z.real))
    return csr_matrix((data, (rows, cols)), shape=(2 * NC, 2 * NV))


def initial_point(rng: np.random.Generator, scale: float) -> np.ndarray:
    x = scale * (rng.standard_normal(NV) + 1j * rng.standard_normal(NV))
    for a, matching in enumerate(MATCHINGS[:3]):
        for i, j in matching:
            x[var_index(i, j, a, a)] += 1.0
    return np.concatenate((x.real, x.imag))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--starts", type=int, default=5)
    ap.add_argument("--max-nfev", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=20260721)
    ap.add_argument("--scale", type=float, default=0.15)
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    best = None
    for start in range(args.starts):
        y0 = initial_point(rng, args.scale)
        t0 = time.time()
        ans = least_squares(
            residual,
            y0,
            jac=jacobian,
            method="trf",
            x_scale="jac",
            ftol=1e-13,
            xtol=1e-13,
            gtol=1e-13,
            max_nfev=args.max_nfev,
            verbose=0,
        )
        r = residual(ans.x)
        maxerr = float(np.max(np.abs(r[:NC] + 1j * r[NC:])))
        norm = float(np.linalg.norm(r))
        elapsed = time.time() - t0
        print(
            f"start={start} status={ans.status} nfev={ans.nfev} "
            f"cost={ans.cost:.12g} norm={norm:.12g} maxerr={maxerr:.12g} "
            f"time={elapsed:.2f}s"
        )
        if best is None or norm < best[0]:
            best = (norm, maxerr, ans.x.copy())

    assert best is not None
    x = unpack(best[2])
    np.savez_compressed("result.npz", x=x, norm=best[0], maxerr=best[1])
    print(f"best norm={best[0]:.12g} maxerr={best[1]:.12g}")


if __name__ == "__main__":
    main()
