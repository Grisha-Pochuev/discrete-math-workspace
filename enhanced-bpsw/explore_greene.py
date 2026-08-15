#!/usr/bin/env python3
"""Explore exact structural subclasses of the Greene--Chen 4838-prime pool.

For Method A* with D=5, P=Q=5, all selected primes are required to have
(5/p)=-1 and the number of selected factors odd.  For each prime p we compute:
  * o2 = ord_p(2)
  * o5 = ord_p(5)
  * rho = rank of apparition of p in Fibonacci sequence
  * t = order in F_{p^2} of alpha=(5+sqrt(5))/2
  * c = lcm(t, 2*o5)
The local conditions m=n/p == 1 (mod c) imply the U, V and Euler-Q
conditions of enhanced BFW modulo p.  Equal 2-adic valuations of o2 and rho
supply the strong base-2 and strong Lucas conditions.
"""
from __future__ import annotations

import argparse
import collections
import html as html_mod
import json
import math
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

import requests
from sympy import factorint, jacobi_symbol

URL = "https://www.d.umn.edu/~jgreene/baillie/Baillie-PSW.html"
M_EXTREME = int(
    "391503310121204881113221826377421073230588550480847994760111"
    "437264285933394797561252633748976272034752759144054959758356"
    "281631740751422332870766577461271728486411722501243608126322"
    "081539854254895422161780480832565829680409393157195431459784"
    "481602760641763660786715059347404742"
)
N_EXTREME = int(
    "234140225752418688005464457713566506358755719892017711133836"
    "422331572174538952682649975569313518021383999970255887289214"
    "770286598356807954528507483688540755157670239035842269509644"
    "277978341717565068329104640284794943619967653440781565902586"
    "799586600590853417916276540721230114816"
)


def v2(n: int) -> int:
    if n <= 0:
        raise ValueError(n)
    return (n & -n).bit_length() - 1


def oddpart(n: int) -> int:
    return n >> v2(n)


def lcm_many(xs: Iterable[int]) -> int:
    ans = 1
    for x in xs:
        ans = math.lcm(ans, int(x))
    return ans


def phi_from_factor(f: dict[int, int]) -> int:
    ans = 1
    for p, e in f.items():
        ans *= (p - 1) * p ** (e - 1)
    return ans


def factor_from_known(n: int, known_primes: list[int]) -> dict[int, int]:
    rem = n
    out: dict[int, int] = {}
    for q in known_primes:
        if q * q > rem:
            break
        if rem % q == 0:
            e = 0
            while rem % q == 0:
                rem //= q
                e += 1
            out[q] = e
        if rem == 1:
            break
    if rem > 1:
        for q, e in factorint(rem).items():
            out[int(q)] = out.get(int(q), 0) + int(e)
    prod = 1
    for q, e in out.items():
        prod *= q**e
    if prod != n:
        raise ArithmeticError((n, out, prod))
    return out


def order_mod(a: int, p: int, fac_pm1: dict[int, int]) -> int:
    order = p - 1
    a %= p
    for q in fac_pm1:
        while order % q == 0 and pow(a, order // q, p) == 1:
            order //= q
    if pow(a, order, p) != 1:
        raise ArithmeticError("bad multiplicative order")
    return order


def fib_pair(n: int, mod: int) -> tuple[int, int]:
    if n == 0:
        return 0, 1
    a, b = fib_pair(n >> 1, mod)
    c = (a * ((2 * b - a) % mod)) % mod
    d = (a * a + b * b) % mod
    if n & 1:
        return d, (c + d) % mod
    return c, d


def fib_rank(p: int, eps5: int, fac_bound: dict[int, int]) -> int:
    rank = p - eps5
    for q in fac_bound:
        while rank % q == 0 and fib_pair(rank // q, p)[0] == 0:
            rank //= q
    if fib_pair(rank, p)[0] != 0:
        raise ArithmeticError(f"bad Fibonacci rank for {p}")
    return rank


def fp2_mul(x: tuple[int, int], y: tuple[int, int], p: int, D: int = 5) -> tuple[int, int]:
    a, b = x
    c, d = y
    return ((a * c + D * b * d) % p, (a * d + b * c) % p)


def fp2_pow(x: tuple[int, int], n: int, p: int, D: int = 5) -> tuple[int, int]:
    r = (1, 0)
    b = x
    while n:
        if n & 1:
            r = fp2_mul(r, b, p, D)
        b = fp2_mul(b, b, p, D)
        n >>= 1
    return r


def alpha_order(p: int, o5: int, rho: int) -> int:
    inv2 = (p + 1) // 2
    alpha = (5 * inv2 % p, inv2 % p)
    candidate = 2 * math.lcm(o5, rho)
    order = candidate
    for q in factorint(candidate):
        q = int(q)
        while order % q == 0 and fp2_pow(alpha, order // q, p) == (1, 0):
            order //= q
    if fp2_pow(alpha, order, p) != (1, 0):
        raise ArithmeticError(f"bad alpha order for {p}")
    return order


def parse_extreme_pool(text: str) -> list[int]:
    text = html_mod.unescape(text)
    sets = re.findall(r"P\s*=\s*\{([^}]+)\}", text, flags=re.S | re.I)
    pools: list[list[int]] = []
    for block in sets:
        vals = [int(x) for x in re.findall(r"\d+", block)]
        if vals:
            pools.append(vals)
    if not pools:
        raise RuntimeError("could not parse prime pools")
    pool = max(pools, key=len)
    if len(pool) != 4838:
        raise RuntimeError(f"expected 4838 primes, parsed {len(pool)}; pool sizes {[len(x) for x in pools]}")
    if len(set(pool)) != len(pool):
        raise RuntimeError("duplicate primes in parsed pool")
    return pool


@dataclass(frozen=True)
class Rec:
    p: int
    o2: int
    o5: int
    rho: int
    alpha_order: int
    c: int
    a2: int
    arho: int
    ac: int
    residue2: int
    kmod: int
    plus_odd: int
    minus_odd: int
    o2_div_M: bool
    rho_div_N: bool
    plus_div_M: bool
    minus_div_N: bool


def order_mod_power_of_two(r: int, a: int) -> int:
    if a <= 1:
        return 1
    mod = 1 << a
    r %= mod
    x = 1
    for k in range(1, (1 << max(0, a - 2)) + 1):
        x = (x * r) % mod
        if x == 1:
            return k
    raise ArithmeticError((r, a))


def compute_record(p: int, known: list[int]) -> Rec | None:
    if int(jacobi_symbol(5, p)) != -1:
        return None
    fm = factor_from_known(p - 1, known)
    fp = factor_from_known(p + 1, known)
    o2 = order_mod(2, p, fm)
    o5 = order_mod(5, p, fm)
    rho = fib_rank(p, -1, fp)
    t = alpha_order(p, o5, rho)
    c = math.lcm(t, 2 * o5)
    ac = v2(c)
    r = p % (1 << ac) if ac else 0
    kmod = order_mod_power_of_two(r, ac)

    plus = oddpart(o2)
    minus = 1
    for q, e in factorint(oddpart(c)).items():
        q, e = int(q), int(e)
        pe = q**e
        if (p - 1) % pe == 0:
            plus = math.lcm(plus, pe)
        elif (p + 1) % pe == 0:
            minus = math.lcm(minus, pe)
        else:
            raise ArithmeticError((p, q, e, c))
    if minus % oddpart(rho) != 0:
        raise ArithmeticError((p, minus, rho))

    return Rec(
        p=p, o2=o2, o5=o5, rho=rho, alpha_order=t, c=c,
        a2=v2(o2), arho=v2(rho), ac=ac, residue2=r, kmod=kmod,
        plus_odd=plus, minus_odd=minus,
        o2_div_M=(M_EXTREME % o2 == 0),
        rho_div_N=(N_EXTREME % rho == 0),
        plus_div_M=(M_EXTREME % plus == 0),
        minus_div_N=(N_EXTREME % minus == 0),
    )


def score_pool(recs: list[Rec]) -> dict:
    lp = lcm_many(r.plus_odd for r in recs)
    lm = lcm_many(r.minus_odd for r in recs)
    fp = {int(q): int(e) for q, e in factorint(lp).items()}
    fm = {int(q): int(e) for q, e in factorint(lm).items()}
    entropy = math.log2(phi_from_factor(fp)) + math.log2(phi_from_factor(fm))
    return {
        "count": len(recs),
        "plus_bits": lp.bit_length(), "minus_bits": lm.bit_length(),
        "plus_phi_log2": math.log2(phi_from_factor(fp)),
        "minus_phi_log2": math.log2(phi_from_factor(fm)),
        "entropy_upper_log2": entropy,
        "surplus_upper": len(recs) - entropy,
        "gcd_plus_minus": math.gcd(lp, lm),
        "plus_factor_count": len(fp), "minus_factor_count": len(fm),
        "all_plus_div_M": all(r.plus_div_M for r in recs),
        "all_minus_div_N": all(r.minus_div_N for r in recs),
        "cardinality_mod": recs[0].kmod if recs else None,
        "class": [recs[0].a2, recs[0].arho, recs[0].ac, recs[0].residue2] if recs else None,
    }


def prune_by_coordinate(recs: list[Rec], rounds: int = 30) -> list[dict]:
    cur = list(recs)
    frontier: list[dict] = []
    for step in range(rounds + 1):
        sc = score_pool(cur)
        sc["step"] = step
        frontier.append(sc)
        if len(cur) < 20:
            break
        lp = lcm_many(r.plus_odd for r in cur)
        lm = lcm_many(r.minus_odd for r in cur)
        fplus = {int(q): int(e) for q, e in factorint(lp).items()}
        fminus = {int(q): int(e) for q, e in factorint(lm).items()}
        options = []
        for side, fac in (("p", fplus), ("m", fminus)):
            for q, e in fac.items():
                pe = q**e
                users = [r for r in cur if ((r.plus_odd if side == "p" else r.minus_odd) % pe == 0)]
                cost = math.log2((q - 1) * q ** (e - 1))
                gain = cost - len(users)
                options.append((gain, cost / max(1, len(users)), side, q, e, users))
        options.sort(key=lambda x: (x[0], x[1]), reverse=True)
        _, _, _, _, _, users = options[0]
        user_set = {r.p for r in users}
        nxt = [r for r in cur if r.p not in user_set]
        if not nxt or len(nxt) == len(cur):
            break
        cur = nxt
    return frontier


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=URL)
    ap.add_argument("--cache", default="enhanced-bpsw/greene-page.html")
    ap.add_argument("--output", default="enhanced-bpsw/exploration.json")
    ap.add_argument("--records", default="enhanced-bpsw/greene-records.jsonl")
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    cache = Path(args.cache)
    cache.parent.mkdir(parents=True, exist_ok=True)
    if cache.exists():
        page = cache.read_text(encoding="utf-8", errors="replace")
    else:
        resp = requests.get(args.url, timeout=120, headers={"User-Agent": "mathematical-research/1.0"})
        resp.raise_for_status()
        page = resp.text
        cache.write_text(page, encoding="utf-8")
    pool = parse_extreme_pool(page)
    print(f"parsed pool: {len(pool)} primes", flush=True)

    fm = factorint(M_EXTREME)
    fn = factorint(N_EXTREME)
    known = sorted(set(map(int, fm)) | set(map(int, fn)))

    records: list[Rec] = []
    started = time.time()
    for idx, p in enumerate(pool, 1):
        r = compute_record(p, known)
        if r is not None:
            records.append(r)
        if idx % 100 == 0:
            print(f"processed {idx}/{len(pool)}; inert={len(records)}; elapsed={time.time()-started:.1f}s", flush=True)

    Path(args.records).parent.mkdir(parents=True, exist_ok=True)
    with open(args.records, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(asdict(r), sort_keys=True) + "\n")

    groups: dict[tuple[int, int, int, int], list[Rec]] = collections.defaultdict(list)
    for r in records:
        groups[(r.a2, r.arho, r.ac, r.residue2)].append(r)

    summaries = []
    for key, rs in groups.items():
        sc = score_pool(rs)
        sc["key"] = list(key)
        summaries.append(sc)
    summaries.sort(key=lambda x: (x["surplus_upper"], x["count"]), reverse=True)

    frontier = []
    for sc in summaries[: max(args.top, 5)]:
        key = tuple(sc["key"])
        frontier.append({"key": list(key), "frontier": prune_by_coordinate(groups[key], rounds=50)})

    out = {
        "source": args.url, "pool_count": len(pool), "inert_count": len(records),
        "M_bits": M_EXTREME.bit_length(), "N_bits": N_EXTREME.bit_length(),
        "M_factor_count": len(fm), "N_factor_count": len(fn),
        "group_count": len(groups), "top_groups": summaries[: args.top],
        "frontiers": frontier,
        "diagnostics": {
            "ord2_div_M": sum(r.o2_div_M for r in records),
            "rho_div_N": sum(r.rho_div_N for r in records),
            "plus_div_M": sum(r.plus_div_M for r in records),
            "minus_div_N": sum(r.minus_div_N for r in records),
        },
        "elapsed_seconds": time.time() - started,
    }
    Path(args.output).write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
