import base64, gzip, hashlib, io, json, lzma, os, subprocess, sys, tarfile, time, urllib.request
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

S = int(sys.argv[1]); T = int(sys.argv[2]); W = int(os.environ.get("W", "4"))
_q = (os.environ.get("Q", "") + ",,,").split(",")
NP = int(_q[0] or 300); NK = int(_q[1] or 30); CY = int(_q[2] or 1)
FIXM = 200000; K = 50; MG = 2
t0 = time.time(); t_end = t0 + T; GD = int(t_end - int(os.environ.get("MS", "900"))); RS = int(os.environ.get("RS", "2400"))
D = Path("wd"); D.mkdir(exist_ok=True); O = Path("o"); O.mkdir(exist_ok=True)
P = Path("p"); Q = Path("q"); H = Path(__file__).with_name("h.bin")
_pt = os.environ.get("PERT", "0")
G = Path(__file__).with_name("g.bin" if _pt in ("", "0") else f"g{_pt}.bin")
B = base64.b64decode("aHR0cHM6Ly93d3cubWF0aC51d2F0ZXJsb28uY2EvdHNwL3N0YXIvZGF0YS9nYWlhMjA3OTQ3MQ==").decode()
I = {"a": (B + ".xyz.txt.gz", "0a613505e22d15f67372824568bce53255b088d677889bc9990299afea5735b4"),
     "b": (B + base64.b64decode("X3RvdXIudHh0Lmd6").decode(), "ab3c6fa0ff96eae12b9b63c8f8654b839e90621f2acc866c18cdf54720b4e852")}


def log(m):
    print(time.strftime("%H:%M:%S ") + m, flush=True)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


if not os.environ.get("LOCAL"):
    for k, (u, h) in I.items():
        p = D / k
        for _ in range(3):
            if p.exists() and sha(p) == h:
                break
            try:
                with urllib.request.urlopen(u, timeout=60) as r_, open(p, "wb") as f_:
                    f_.write(r_.read())
            except Exception as e:
                log(f"in {k}: {e}"); time.sleep(20)
        assert sha(p) == h, k
    X = np.loadtxt(gzip.open(D / "a", "rt"))
    R = np.loadtxt(gzip.open(D / "b"), dtype=np.int64) - 1
else:
    X = np.load(os.environ["LOCAL"] + "/X.npy"); R = np.load(os.environ["LOCAL"] + "/R.npy") - 1
N = len(X)


def ln(a, b):
    return np.floor(np.sqrt(((X[a] - X[b]) ** 2).sum(-1)) + 0.5).astype(np.int64)


def L(t):
    assert len(t) == N and np.array_equal(np.sort(t), np.arange(N))
    return int(ln(t, np.roll(t, -1)).sum())


g = np.load(io.BytesIO(G.read_bytes()))
if "dr" in g.files:
    _A = np.empty((N, 2), np.int64); _A[R, 0] = np.roll(R, 1); _A[R, 1] = np.roll(R, -1)
    for u, v in g["dr"].astype(np.int64):
        _A[u][_A[u] == v] = -1; _A[v][_A[v] == u] = -1
    for u, v in g["da"].astype(np.int64):
        _A[u, np.where(_A[u] < 0)[0][0]] = v; _A[v, np.where(_A[v] < 0)[0][0]] = u
    _Al = _A.tolist(); _t = [0] * N; _p = _Al[int(R[0])][0]; _c = int(R[0])
    for _k in range(N):
        _t[_k] = _c; _a = _Al[_c]; _n = _a[0] if _a[0] != _p else _a[1]; _p, _c = _c, _n
    _b0 = L(R); R = np.array(_t, np.int64); log(f"base {L(R) - _b0}")
R0 = L(R)
pos = np.empty(N, np.int64); pos[R] = np.arange(N)
if "o" in g.files:
    _o = g["o"].astype(np.int64); RI = S % (len(_o) - 1)
    ids = g["i"][_o[RI]:_o[RI + 1]].astype(np.int64)
else:
    RI = -1; ids = g["i"].astype(np.int64)
Lc = ids[np.argsort(pos[ids])]; n = len(Lc); pc = pos[Lc]
fx = ((np.roll(pc, -1) - pc) % N) != 1
Xr = X[Lc]
li = np.arange(n); lj = (li + 1) % n
FL0 = int(ln(Lc[li[~fx]], Lc[lj[~fx]]).sum())
fi = np.where(fx)[0]; F = np.stack([fi, (fi + 1) % n], 1).astype(np.int32)
REF = FL0 - FIXM * len(F)
fkey = np.sort(np.minimum(F[:, 0], F[:, 1]).astype(np.int64) * n + np.maximum(F[:, 0], F[:, 1]))
_, nn = cKDTree(Xr).query(Xr, k=K + 1)
NN = np.empty((n, K), np.int32)
for i in range(n):
    r = nn[i][nn[i] != i][:K]; NN[i] = r
with open(D / "g.inst", "wb") as fh:
    np.array([n, len(F), K], np.int32).tofile(fh); Xr.astype(np.float64).tofile(fh); F.tofile(fh); NN.tofile(fh)
(D / "r.txt").write_text(f"{n} 0\n" + " ".join(map(str, range(1, n + 1))) + "\n")
x = D / "x"
if not x.exists():
    sd = D / "src"; sd.mkdir(exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(lzma.decompress(g["s"].tobytes()))) as tf:
        tf.extractall(sd)
    cx = os.environ.get("CXX", "g++ -O3 -march=native").split()
    subprocess.run([*cx, "-w", "-o", str(x), *map(str, sorted(sd.glob("*.cpp"))), "-lm"], check=True)
log(f"ok f={len(F)} {time.time() - t0:.0f}s")


def fl(t):
    a = np.asarray(t, np.int64); b = np.roll(a, -1)
    k = np.minimum(a, b) * n + np.maximum(a, b)
    isf = np.isin(k, fkey)
    if isf.sum() != len(fkey) or not np.isin(fkey, k).all():
        return None
    return int(ln(Lc[a[~isf]], Lc[b[~isf]]).sum())


def ekeys(t):
    a = np.asarray(t, np.int64); b = np.roll(a, -1)
    return np.unique(np.minimum(a, b) * n + np.maximum(a, b))


RK = ekeys(np.arange(n))


def enc(ps, hdr=None):
    A = np.full((len(ps), n), 255, np.uint8); ex = []
    for j, t in enumerate(ps):
        s = np.empty(n, np.int64); s[t] = np.roll(t, -1)
        hit = NN == s[:, None]; ok = hit.any(1); r = hit.argmax(1)
        A[j, ok] = r[ok]; bad = np.where(~ok)[0]
        ex.append(np.stack([np.full(len(bad), j), bad, s[bad]], 1))
    E = np.concatenate(ex).astype(np.int64) if ex else np.zeros((0, 3), np.int64)
    buf = io.BytesIO(); np.savez(buf, a=A, e=E, h=np.array(hdr or [], dtype="U16"))
    return lzma.compress(buf.getvalue(), preset=6)


def dec(b):
    z = np.load(io.BytesIO(lzma.decompress(b)))
    A, E, hdr = z["a"], z["e"], [str(v) for v in z["h"]]
    out = []
    for j in range(len(A)):
        s = np.where(A[j] < 255, NN[np.arange(n), np.minimum(A[j], K - 1)], -1).astype(np.int64)
        e = E[E[:, 0] == j]; s[e[:, 1]] = e[:, 2]
        t = np.empty(n, np.int64); c = 0
        sl = s.tolist(); tl = [0] * n
        for i in range(n):
            tl[i] = c; c = sl[c]
        t[:] = tl
        out.append(t)
    return hdr, out


def rd(path):
    tx = Path(path).read_text(); hdr = None
    if tx.startswith("CKPT"):
        h, tx = tx.split("\n", 1); hdr = h.split()[1:11]
    a = np.array(tx.split(), np.int64) if len(tx) < 1000 else np.fromstring(tx, dtype=np.int64, sep=" ")
    ps = []; i = 0
    while i < len(a):
        m = int(a[i]); ps.append(a[i + 2:i + 2 + m] - 1); i += 2 + m
    return hdr, ps


def wr(path, ps, hdr=None):
    with open(path, "w") as f:
        if hdr:
            f.write("CKPT " + " ".join(hdr) + "\n")
        for t in ps:
            f.write(f"{n} 0\n" + " ".join(map(str, np.asarray(t) + 1)) + "\n")


def mig(src):
    out = []
    for p in src:
        if p.exists():
            try:
                out += dec(p.read_bytes())[1]
            except Exception as e:
                log(f"m {p.name}: {e}")
    return out


st_p = P / "st.json"
st = json.loads(st_p.read_text()) if st_p.exists() else {"isl": {}}
M_in = (mig([Q / "m.bin"]) + mig([H])) if RI < 0 else mig([P / "m.bin"])
_ap = Path(__file__).with_name(f"a{_pt}_{RI}.bin")
AP = [t for t in mig([_ap if _ap.exists() else Path(__file__).with_name("a.bin")]) if fl(t) is not None]
AV = os.environ.get("AV", "1") == "1" and _ap.exists()
log(f"in p={int(st_p.exists())} m={len(M_in)} a={len(AP)}")
rep = {"s": S, "ri": RI, "cy": CY, "gain": 0, "isl": [], "imp": []}
best_full = None


def setup(k, fresh):
    I_ = W * S + k
    e = st["isl"].get(str(k), {"tr": 0})
    if fresh:
        e = {"tr": e.get("tr", -1) + 1}
    tr = e["tr"]; mode = "a" if (I_ + tr) % 4 == 0 else "b"
    e["mode"] = mode
    d = D / f"i{k}"; d.mkdir(exist_ok=True)
    for f_ in d.glob("imp*.txt"):
        f_.unlink()
    pf = "-"
    ck = P / f"c{k}.bin"
    if not fresh and ck.exists():
        hdr, ps = dec(ck.read_bytes())
        if hdr and hdr[-1] == "done":
            return setup(k, True)
        if hdr and int(hdr[8]) == len(ps) == NP and M_in:
            v = [fl(t) for t in ps]; o_ = np.argsort(v)[::-1]; have = set(v); j = 0
            for t in M_in:
                if j >= MG:
                    break
                vt = fl(t)
                if vt is not None and vt not in have and vt < v[o_[j]]:
                    ps[o_[j]] = t; have.add(vt); j += 1
            e["mig"] = j
        wr(d / "in.txt", ps, hdr); pf = str(d / "in.txt")
    elif AP and AV and k % 2 == 0:
        mode = e["mode"] = "v"
        wr(d / "in.txt", [np.arange(n)] + AP); pf = str(d / "in.txt")
    elif AP and not AV:
        mode = e["mode"] = "s"
        rs = np.random.default_rng(1000 * I_ + tr + 100 * CY)
        pick = rs.choice(len(AP), size=min(NP - 1, len(AP)), replace=False)
        wr(d / "in.txt", [np.arange(n)] + [AP[j] for j in pick]); pf = str(d / "in.txt")
    elif mode == "a":
        pf = str(D / "r.txt")
    env = dict(os.environ, GA_CKSEC="1200", GA_LIVE=str(d / "live.txt"))
    if mode == "s":
        env["GA_START2"] = "1"
    if mode == "b":
        env["GA_INJECT"] = str(D / "r.txt")
    seed = 1000 * I_ + 7 * tr + CY
    lf = open(O / f"l{k}_{tr}.txt", "a")
    pr = subprocess.Popen([str(x), str(D / "g.inst"), str(d), str(NP), str(NK), str(seed), str(GD), str(REF), pf],
                          stdout=lf, stderr=subprocess.STDOUT, env=env)
    st["isl"][str(k)] = e
    return pr, lf


def last(k):
    e = st["isl"][str(k)]
    p = O / f"l{k}_{e['tr']}.txt"
    try:
        ls = [l for l in p.read_text().splitlines() if l.startswith("g ") or l.startswith("init ")]
        return ls[-1] if ls else ""
    except Exception:
        return ""


def chk_imp(k):
    global best_full
    for f_ in sorted((D / f"i{k}").glob("imp*.txt")):
        _, ps = rd(f_)
        f_.rename(f_.with_suffix(".done"))
        for t in ps:
            v = fl(t)
            if v is None or v >= FL0:
                continue
            tt = t.tolist()
            full = []
            for a_ in range(n):
                uu, vv = tt[a_], tt[(a_ + 1) % n]
                full.append(int(Lc[uu]))
                if vv == (uu + 1) % n and fx[uu]:
                    a, b = pc[uu], pc[vv]; m = (b - a - 1) % N
                    if m: full.extend(R[(a + 1 + np.arange(m)) % N].tolist())
                elif uu == (vv + 1) % n and fx[vv]:
                    a, b = pc[vv], pc[uu]; m = (b - a - 1) % N
                    if m: full.extend(R[(a + 1 + np.arange(m)) % N][::-1].tolist())
            full = np.array(full, np.int64)
            gn = R0 - L(full)
            log(f"IMP {k} {gn} {FL0 - v}")
            rep["imp"].append({"k": k, "gain": gn, "local": FL0 - v})
            if gn > 0 and gn > rep["gain"]:
                rep["gain"] = gn; best_full = full
                with gzip.open(O / f"t{gn}.txt.gz", "wt") as f2:
                    f2.write("\n".join(map(str, full + 1)) + "\n")
                (O / "s.json").write_text(json.dumps(rep, separators=(",", ":")))



# ---- live exchange (hourly): export island bests to branch x<S>-<run>, import r85/x<pert>_<RI>.bin
LP = int(os.environ.get("LP", "3600")); RP = os.environ.get("GITHUB_REPOSITORY", ""); RUN = os.environ.get("GITHUB_RUN_ID", "0")
XU = os.environ.get("XU", f"https://raw.githubusercontent.com/{RP}/main/r85/x{_pt}_{RI}.bin")
xseen = set(); xn = [time.time() + LP]; xc = [0]


def xpack(ps):
    b_ = io.BytesIO(); np.savez(b_, t=np.array(ps, np.int32)); return lzma.compress(b_.getvalue())


def xunpack(b):
    return [np.asarray(t, np.int64) for t in np.load(io.BytesIO(lzma.decompress(b)))["t"]]


def xchg():
    out = []
    for k in range(W):
        ck = D / f"i{k}" / "ck.txt"
        try:
            _, ps = rd(ck); v = [fl(t) for t in ps]; o_ = np.argsort([1e18 if a is None else a for a in v]); sv = set()
            for j in o_:
                if len(sv) >= 3: break
                if v[j] is not None and v[j] not in sv: sv.add(v[j]); out.append(ps[j])
        except Exception as e:
            log(f"xe {k}: {e}")
    if out:
        (O / "xh.bin").write_bytes(xpack(out))
        tk = os.environ.get("GH_TOKEN", "")
        if tk and RP:
            try:
                w_ = Path("xw"); w_.mkdir(exist_ok=True); (w_ / "x.bin").write_bytes(xpack(out))
                cmd = f"cd xw && rm -rf .git && git init -q && git add x.bin && git -c user.name=r85 -c user.email=r85@users.noreply.github.com commit -qm x && git push -qf https://x-access-token:{tk}@github.com/{RP} HEAD:refs/heads/x{S}-{RUN}"
                subprocess.run(cmd, shell=True, check=True, timeout=120); log(f"xo {len(out)} " + " ".join(str(fl(t) - FL0) for t in out))
            except Exception as e:
                log(f"xo err {e}")
    try:
        with urllib.request.urlopen(XU, timeout=60) as r_:
            b = r_.read()
        h_ = hashlib.sha256(b).hexdigest()
        if h_ not in xseen:
            xseen.add(h_); got = 0
            for t in xunpack(b):
                vt = fl(t)
                if vt is None: continue
                k = xc[0] % W; xc[0] += 1
                wr(D / f"i{k}" / "live.tmp", [t]); os.replace(D / f"i{k}" / "live.tmp", D / f"i{k}" / "live.txt"); got += 1
                if got >= W: break
            log(f"xi {got}")
    except Exception as e:
        if "404" not in str(e): log(f"xi err {e}")

procs = {k: setup(k, False) for k in range(W)}
gone = set(); nl = 0
while True:
    time.sleep(30)
    alive = 0
    for k in range(W):
        pr, lf = procs[k]
        chk_imp(k)
        if pr.poll() is None:
            alive += 1; continue
        if k in gone:
            continue
        gone.add(k)
        if time.time() < GD - RS:
            tg = st["isl"][str(k)]
            try:
                hdr, ps = rd(D / f"i{k}" / "ck.txt")
                if hdr and hdr[-1] == "done":
                    lf.close()
                    v = [fl(t) for t in ps]; o_ = np.argsort(v)[:30]
                    (O / f"f{k}_{tg['tr']}.bin").write_bytes(enc([ps[j] for j in o_], hdr))
                    log(f"fin {k} {tg['tr']} b={min(v) - FL0} a={np.mean(v) - FL0:.1f}")
                    (D / f"i{k}" / "ck.txt").unlink()
                    procs[k] = setup(k, True); gone.discard(k); alive += 1
                else:
                    log(f"x {k} rc={pr.returncode}")
            except Exception as e:
                log(f"x {k}: {e}")
    if time.time() - t0 > nl:
        log(" | ".join(f"{k}:{st['isl'][str(k)]['mode']}{st['isl'][str(k)]['tr']} {last(k)}" for k in range(W)))
        nl = time.time() - t0 + 600
    if time.time() > xn[0] and time.time() < GD - min(300, LP):
        xn[0] = time.time() + LP; xchg()
    if alive == 0:
        break
for k in range(W):
    try:
        procs[k][1].close()
    except Exception:
        pass
    chk_imp(k)
migr = []
for k in range(W):
    e = st["isl"][str(k)]
    ck = D / f"i{k}" / "ck.txt"
    r_ = {"k": k, "mode": e["mode"], "tr": e["tr"], "mig": e.get("mig", 0)}
    if ck.exists() and len(rd(ck)[1]) > 0:
        hdr, ps = rd(ck)
        (O / f"c{k}.bin").write_bytes(enc(ps, hdr))
        v = np.array([fl(t) for t in ps], dtype=float)
        o_ = np.argsort(v)
        U = np.unique(np.concatenate([ekeys(t) for t in ps]))
        nu = np.setdiff1d(U, RK)
        (O / f"u{k}.bin").write_bytes(lzma.compress(np.stack([nu // n, nu % n], 1).astype(np.int32).tobytes()))
        nb = [int(len(np.setdiff1d(ekeys(ps[j]), RK))) for j in o_[:5]]
        r_.update({"g": int(hdr[0]), "st": int(hdr[1]), "tag": hdr[-1], "np": len(ps), "b": float(v.min() - FL0),
                   "a": float(v.mean() - FL0), "q": [float(v[j] - FL0) for j in o_[:10]], "ne": int(len(nu)), "nb": nb})
        seen = set()
        for j in o_:
            if len(seen) >= 3:
                break
            if v[j] not in seen and v[j] != FL0:
                seen.add(v[j]); migr.append(ps[j])
    rep["isl"].append(r_)
    log(f"end {k} " + json.dumps({a: r_[a] for a in r_ if a not in ("q",)}))
if migr:
    (O / "m.bin").write_bytes(enc(migr))
(O / "st.json").write_text(json.dumps(st))
(O / "s.json").write_text(json.dumps(rep, separators=(",", ":")))
for f_ in O.glob("l*.txt"):
    with open(f_, "rb") as a, gzip.open(str(f_) + ".gz", "wb") as b:
        b.write(a.read())
    f_.unlink()
log(f"done gain={rep['gain']}")
