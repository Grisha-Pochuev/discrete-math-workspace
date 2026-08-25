#!/usr/bin/env python3
"""Lattice attack on Zhang's 1029-prime Williams-number system.

Builds either a Coster/Kannan embedding or a CVP instance for the exact
simultaneous modular equations.  Any emitted certificate is checked twice:
against the modular model and directly against p-1 | N-1, p+1 | N+1.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
import sys
from pathlib import Path
from typing import Iterable

sys.set_int_max_str_digits(1_000_000)

NVAR = 1029


def load_rows(weight: int | None) -> list[dict]:
    raw = json.loads(Path("global_rows.json").read_text())
    rows: list[dict] = []
    for r in raw:
        m = int(r["m"])
        a = [int(z) % m for z in r["a"]]
        b = int(r.get("b", 0)) % m
        rows.append({"name": str(r.get("name", "row")), "m": m, "a": a, "b": b})

    # The transformed plus-side coordinates use log(-p), so odd cardinality
    # is an explicit part of the equivalent system.
    if weight is None:
        rows.append({"name": "odd_cardinality", "m": 2, "a": [1] * NVAR, "b": 1})
    else:
        if not (3 <= weight <= NVAR and weight % 2 == 1):
            raise ValueError("weight must be an odd integer between 3 and 1029")
        # Since 0 <= sum x_i <= 1029, congruence mod 1030 is exact equality.
        rows.append({"name": f"weight_{weight}", "m": 1030, "a": [1] * NVAR, "b": weight})
    return rows


def signed(z: int, m: int) -> int:
    z %= m
    return z if z <= m // 2 else z - m


def write_matrix(path: Path, matrix: Iterable[list[int]]) -> None:
    with path.open("w") as f:
        f.write("[")
        first = True
        for row in matrix:
            if not first:
                f.write("\n ")
            first = False
            f.write("[" + " ".join(map(str, row)) + "]")
        f.write("\n]\n")


def build(args: argparse.Namespace) -> None:
    rows = load_rows(args.weight)
    R = len(rows)
    scale = int(args.scale)
    if scale <= 0:
        raise ValueError("scale must be positive")

    coeff = [[signed(int(r["a"][i]), int(r["m"])) for r in rows] for i in range(NVAR)]
    target = [signed(int(r["b"]), int(r["m"])) for r in rows]

    order = list(range(NVAR + R))
    if args.order == "shuffled":
        random.Random(args.seed).shuffle(order)
    elif args.order == "modfirst":
        order = list(range(NVAR, NVAR + R)) + list(range(NVAR))

    base_rows: list[list[int]] = []
    for key in order:
        v = [0] * (NVAR + R)
        if key < NVAR:
            i = key
            v[i] = 2
            for r in range(R):
                v[NVAR + r] = scale * coeff[i][r]
        else:
            r = key - NVAR
            v[NVAR + r] = scale * int(rows[r]["m"])
        base_rows.append(v)

    meta = {
        "n": NVAR,
        "row_count": R,
        "scale": scale,
        "embed": int(args.embed),
        "weight": args.weight,
        "seed": args.seed,
        "order": args.order,
        "rows": [{"name": r["name"], "m": r["m"], "b": r["b"]} for r in rows],
        "target": [1] * NVAR + [scale * z for z in target],
    }

    if args.kind == "cvp":
        write_matrix(Path(args.output), base_rows)
        with Path(args.cvp_output).open("w") as f:
            # fplll CVP syntax is [basis][target].
            f.write(Path(args.output).read_text().rstrip() + "\n")
            f.write("[" + " ".join(map(str, meta["target"])) + "]\n")
        meta["rank"] = len(base_rows)
        meta["ambient_dimension"] = len(base_rows[0])
    else:
        T = int(args.embed)
        if T <= 0:
            raise ValueError("embed must be positive")
        matrix = [v + [0] for v in base_rows]
        matrix.append(meta["target"] + [T])
        write_matrix(Path(args.output), matrix)
        meta["rank"] = len(matrix)
        meta["ambient_dimension"] = len(matrix[0])

    Path(args.meta).write_text(json.dumps(meta, indent=2))
    log2_det = NVAR + sum(math.log2(int(r["m"])) for r in rows) + R * math.log2(scale)
    if args.kind == "embed":
        log2_det += math.log2(int(args.embed))
    d = int(meta["rank"])
    gh = math.sqrt(d / (2.0 * math.pi * math.e)) * 2.0 ** (log2_det / d)
    desired = math.sqrt(NVAR + (int(args.embed) ** 2 if args.kind == "embed" else 0))
    print(json.dumps({
        "kind": args.kind,
        "rank": meta["rank"],
        "ambient": meta["ambient_dimension"],
        "rows": R,
        "log2_det_estimate": log2_det,
        "gaussian_heuristic_estimate": gh,
        "desired_vector_norm": desired,
        "desired_over_gh": desired / gh,
    }, indent=2))


def parse_vectors(path: Path, dim: int) -> list[list[int]]:
    text = path.read_text(errors="ignore")
    vals = [int(s) for s in re.findall(r"[-+]?\d+", text)]
    if not vals:
        return []
    if len(vals) % dim != 0:
        raise ValueError(f"cannot parse {path}: {len(vals)} integers is not divisible by dimension {dim}")
    return [vals[i:i + dim] for i in range(0, len(vals), dim)]


def load_primes() -> list[int]:
    candidates = [Path("SET-1029-PRIMES.txt"), Path("primes.txt")]
    for pth in candidates:
        if pth.exists():
            vals = [int(s) for s in re.findall(r"\d+", pth.read_text())]
            if len(vals) == NVAR:
                return vals
    pjson = Path("primes.json")
    if pjson.exists():
        obj = json.loads(pjson.read_text())
        vals = [int(z) for z in obj]
        if len(vals) == NVAR:
            return vals
    fjson = Path("factors.json")
    if fjson.exists():
        obj = json.loads(fjson.read_text())
        vals: list[int] = []
        if isinstance(obj, list):
            for z in obj:
                if isinstance(z, dict) and "p" in z:
                    vals.append(int(z["p"]))
        elif isinstance(obj, dict):
            if "primes" in obj:
                vals = [int(z) for z in obj["primes"]]
            elif all(str(k).isdigit() for k in obj):
                vals = sorted(int(k) for k in obj)
        if len(vals) == NVAR:
            return vals
    raise FileNotFoundError("could not recover the official 1029 primes")


def exact_verify(x: list[int], meta: dict, output: Path) -> bool:
    if len(x) != NVAR or any(z not in (0, 1) for z in x):
        return False
    selected_idx = [i for i, z in enumerate(x) if z]
    if len(selected_idx) < 3 or len(selected_idx) % 2 == 0:
        return False

    rows = load_rows(meta.get("weight"))
    for r in rows:
        if sum(int(a) * int(z) for a, z in zip(r["a"], x)) % int(r["m"]) != int(r["b"]) % int(r["m"]):
            return False

    primes = load_primes()
    selected = [primes[i] for i in selected_idx]
    big_n = math.prod(selected)
    checks = []
    for p in selected:
        okm = (big_n - 1) % (p - 1) == 0
        okp = (big_n + 1) % (p + 1) == 0
        checks.append({"p": p, "minus": okm, "plus": okp})
        if not (okm and okp):
            return False

    cert = {
        "status": "VERIFIED_WILLIAMS_NUMBER",
        "factor_count": len(selected),
        "selected_indices_zero_based": selected_idx,
        "prime_factors": selected,
        "N": str(big_n),
        "direct_checks": checks,
        "model": meta,
    }
    output.write_text(json.dumps(cert, indent=2))
    Path(str(output) + ".factors.txt").write_text("\n".join(map(str, selected)) + "\n")
    Path(str(output) + ".N.txt").write_text(str(big_n) + "\n")
    print("FOUND_VERIFIED", len(selected), output)
    return True


def candidate_from_difference(diff: list[int], meta: dict) -> list[int] | None:
    n = int(meta["n"])
    R = int(meta["row_count"])
    kind = meta.get("kind")
    if len(diff) < n + R:
        return None
    if any(z != 0 for z in diff[n:n + R]):
        return None
    if any(abs(z) != 1 for z in diff[:n]):
        return None
    return [(z + 1) // 2 for z in diff[:n]]


def score_embedding(v: list[int], meta: dict) -> tuple[int, int, int, int]:
    n = int(meta["n"])
    R = int(meta["row_count"])
    T = int(meta["embed"])
    last = abs(abs(v[-1]) - T)
    binary_bad = sum(abs(abs(z) - 1) for z in v[:n])
    residual_bad = sum(abs(z) for z in v[n:n + R])
    norm1 = sum(abs(z) for z in v)
    return last, residual_bad, binary_bad, norm1


def scan(args: argparse.Namespace) -> None:
    meta = json.loads(Path(args.meta).read_text())
    meta["kind"] = args.kind
    n = int(meta["n"])
    R = int(meta["row_count"])
    out = Path(args.certificate)

    if args.kind == "cvp":
        vecs = parse_vectors(Path(args.input), n + R)
        if not vecs:
            print("NO_CVP_VECTOR")
            return
        target = [int(z) for z in meta["target"]]
        for y in vecs:
            for diff in ([a - b for a, b in zip(y, target)], [b - a for a, b in zip(y, target)]):
                x = candidate_from_difference(diff, meta)
                if x is not None and exact_verify(x, meta, out):
                    return
        d = [a - b for a, b in zip(vecs[0], target)]
        print("CVP_MISS", {
            "binary_bad": sum(abs(abs(z) - 1) for z in d[:n]),
            "residual_l1": sum(abs(z) for z in d[n:n + R]),
            "distance_sq": sum(z * z for z in d),
        })
        return

    dim = n + R + 1
    vecs = parse_vectors(Path(args.input), dim)
    if not vecs:
        print("NO_REDUCED_BASIS")
        return

    # Direct basis-vector scan.
    for v in vecs:
        for d in (v, [-z for z in v]):
            if abs(d[-1]) != int(meta["embed"]):
                continue
            x = candidate_from_difference(d, meta)
            if x is not None and exact_verify(x, meta, out):
                return

    # Pair scan among the shortest output vectors.  LLL/BKZ occasionally
    # leaves the wanted embedding vector as the sum of two reduced rows.
    ranked = sorted(vecs, key=lambda v: sum(z * z for z in v))[: min(args.pair_limit, len(vecs))]
    T = int(meta["embed"])
    by_last: dict[int, list[list[int]]] = {}
    for v in ranked:
        by_last.setdefault(v[-1], []).append(v)
    tested = 0
    for lv, left in by_last.items():
        for target_last in (T, -T):
            right = by_last.get(target_last - lv, [])
            for u in left:
                for v in right:
                    tested += 1
                    d = [a + b for a, b in zip(u, v)]
                    x = candidate_from_difference(d, meta)
                    if x is not None and exact_verify(x, meta, out):
                        return
                    if tested >= args.max_pairs:
                        break
                if tested >= args.max_pairs:
                    break
            if tested >= args.max_pairs:
                break
        if tested >= args.max_pairs:
            break

    best = sorted((score_embedding(v, meta), i) for i, v in enumerate(vecs))[:10]
    print("EMBED_MISS", {"vectors": len(vecs), "pairs_tested": tested, "best_scores": best})


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build")
    b.add_argument("--kind", choices=["embed", "cvp"], default="embed")
    b.add_argument("--scale", type=int, default=512)
    b.add_argument("--embed", type=int, default=8)
    b.add_argument("--weight", type=int)
    b.add_argument("--seed", type=int, default=1)
    b.add_argument("--order", choices=["natural", "shuffled", "modfirst"], default="natural")
    b.add_argument("--output", default="lattice.txt")
    b.add_argument("--cvp-output", default="cvp_input.txt")
    b.add_argument("--meta", default="lattice_meta.json")
    b.set_defaults(func=build)

    s = sub.add_parser("scan")
    s.add_argument("--kind", choices=["embed", "cvp"], required=True)
    s.add_argument("--input", required=True)
    s.add_argument("--meta", default="lattice_meta.json")
    s.add_argument("--certificate", default="lattice_certificate.json")
    s.add_argument("--pair-limit", type=int, default=180)
    s.add_argument("--max-pairs", type=int, default=200000)
    s.set_defaults(func=scan)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
