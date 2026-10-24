import base64, gzip, hashlib, io, json, os, subprocess, sys, tarfile, time, urllib.request
from pathlib import Path

import numpy as np

S = int(sys.argv[1]); T = int(sys.argv[2]); W = int(os.environ.get("W", "4"))
Q = os.environ.get("Q", "10000,20000,30000,50000").split(",")
TL = {10000: 900, 20000: 1500, 30000: 2100, 50000: 3300}
D = Path("wd"); D.mkdir(exist_ok=True); O = Path("o"); O.mkdir(exist_ok=True)
Z = Path(__file__).with_name("z.bin")
B = base64.b64decode("aHR0cHM6Ly93d3cubWF0aC51d2F0ZXJsb28uY2EvdHNwL3N0YXIvZGF0YS9nYWlhMjA3OTQ3MQ==").decode()
I = {"a": (B + ".xyz.txt.gz", "0a613505e22d15f67372824568bce53255b088d677889bc9990299afea5735b4"),
     "b": (B + base64.b64decode("X3RvdXIudHh0Lmd6").decode(), "ab3c6fa0ff96eae12b9b63c8f8654b839e90621f2acc866c18cdf54720b4e852")}
K = [base64.b64decode(x).decode() for x in (
    "aHR0cDovL3dlYmhvdGVsNC5ydWMuZGsvfmtlbGQvcmVzZWFyY2gvTEtILTMvTEtILTMuMC4xMy50Z3o=",
    "aHR0cHM6Ly9naXRodWIuY29tL2NlcmViaXMvTEtIMy5naXQ=")]
t_end = time.time() + T


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


R0 = L(R)
x = D / "x"
if os.environ.get("XB"):
    x = Path(os.environ["XB"])
elif not x.exists():
    src = None
    try:
        with urllib.request.urlopen(K[0], timeout=20) as r_, open(D / "k.tgz", "wb") as f_:
            f_.write(r_.read())
        with tarfile.open(D / "k.tgz") as tf:
            tf.extractall(D)
        src = next(D.glob("*/SRC"))
    except Exception as e:
        log(f"k0: {e}")
        subprocess.run(["git", "clone", "-q", "--depth", "1", K[1], str(D / "kg")], check=True)
        src = D / "kg" / "SRC"
    subprocess.run(["gcc", "-O3", "-march=native", "-fcommon", "-w", "-I", str(src / "INCLUDE"), "-o", str(x),
                    *map(str, src.glob("*.c")), "-lm"], check=True)
log("ok")

z = np.load(io.BytesIO(Z.read_bytes()))
zn, zg, zw = z["a"].astype(np.int64), z["b"].astype(np.int64), z["c"].astype(np.float64)
gi = np.argsort(zg, kind="stable"); zn, zg = zn[gi], zg[gi]
gs = np.searchsorted(zg, np.arange(len(zw) + 1))
rng = np.random.default_rng(7919 * S + 13)

best, bl = R.copy(), R0
pos = np.empty(N, np.int64); pos[best] = np.arange(N)
if int(os.environ.get("PERT", "0")):  # fire test: worsened start
    for _ in range(int(os.environ["PERT"])):
        a = pos[int(zn[rng.integers(len(zn))])]; k = int(rng.integers(5, 40))
        if a + k < N:
            best[a:a + k] = best[a:a + k][::-1].copy()
    pos[best] = np.arange(N); bl = L(best); R0 = bl; log("pert")
st = {"s": S, "w": [], "gain": 0}
run, j = {}, 0


def save():
    st["gain"] = R0 - bl
    (O / "s.json").write_text(json.dumps(st, separators=(",", ":")))


RQ = []


def make(j):
    if RQ:
        g, c, m = RQ.pop()
    else:
        g = int(rng.choice(len(zw), p=zw / zw.sum()))
        c = int(zn[gs[g] + rng.integers(gs[g + 1] - gs[g])])
        m = int(Q[(S + j) % len(Q)])
    dd = ((X - X[c]) ** 2).sum(1)
    sel = np.argpartition(dd, m)[:m]
    p = np.sort(pos[sel]); v = best[p]
    nxt = np.roll(p, -1); real = ((nxt - p) % N) == 1
    d = D / f"j{j}"; d.mkdir(exist_ok=True)
    fx = [(i + 1, (i + 1) % m + 1) for i in np.where(~real)[0]]
    with open(d / "g.p", "w") as f:
        f.write(f"TYPE : TSP\nDIMENSION : {m}\nEDGE_WEIGHT_TYPE : EUC_3D\nNODE_COORD_SECTION\n")
        f.write("".join(f"{i + 1} {a:.10g} {b:.10g} {cc:.10g}\n" for i, (a, b, cc) in enumerate(X[v])))
        f.write("FIXED_EDGES_SECTION\n" + "".join(f"{a} {b}\n" for a, b in fx) + "-1\nEOF\n")
    (d / "s.tour").write_text(f"TYPE : TOUR\nDIMENSION : {m}\nTOUR_SECTION\n" + "\n".join(map(str, range(1, m + 1))) + "\n-1\nEOF\n")
    tl = int(os.environ.get("TLX", "0")) or TL.get(m, 1800)
    tl = max(60, min(tl, int(t_end - time.time()) - 60))
    (d / "p").write_text("\n".join([
        f"PROBLEM_FILE = {d / 'g.p'}", f"INITIAL_TOUR_FILE = {d / 's.tour'}",
        "MOVE_TYPE = 5", "MAX_CANDIDATES = 6", "CANDIDATE_SET_TYPE = POPMUSIC", "INITIAL_PERIOD = 1000",
        f"MAX_TRIALS = {int(os.environ.get('MT', '0')) or m}", "STOP_AT_OPTIMUM = NO", "RUNS = 1",
        f"SEED = {1 + S * 1009 + j}", f"TIME_LIMIT = {tl}",
        f"OUTPUT_TOUR_FILE = {d / 'o.tour'}", "TRACE_LEVEL = 1", ""]))
    pr = subprocess.Popen([str(x), str(d / "p")], stdout=open(d / "l", "w"), stderr=subprocess.STDOUT)
    return pr, d, {"j": j, "c": c, "g": g, "n": m, "f": len(fx)}, v, real, time.time()


def rt(p):
    s = p.read_text().split("TOUR_SECTION")[1].split()
    t = []
    for q in s:
        q = int(q)
        if q == -1:
            break
        t.append(q - 1)
    return np.array(t, dtype=np.int64)


def apply(rem, add):
    # apply an exchange to the current best; None if it no longer fits
    nb = np.stack([np.roll(best, 1), np.roll(best, -1)], 1)
    nbr = np.empty_like(nb); nbr[best] = nb
    for a, b in rem:
        for u, w in ((a, b), (b, a)):
            r_ = np.where(nbr[u] == w)[0]
            if not len(r_):
                return None
            nbr[u, r_[0]] = -1
    for a, b in add:
        for u, w in ((a, b), (b, a)):
            r_ = np.where(nbr[u] == -1)[0]
            if not len(r_):
                return None
            nbr[u, r_[0]] = w
    t = np.empty(N, np.int64); prev, cur = -1, int(best[0])
    nl = nbr.tolist()
    for i in range(N):
        t[i] = cur; a, b = nl[cur]
        nx = a if a != prev else b
        prev, cur = cur, nx
    if cur != t[0] or len(np.unique(t)) != N:
        return None
    return t


def finish(pr, d, rec, v, real):
    global best, bl, pos
    m = len(v)
    try:
        t = rt(d / "o.tour")
        assert len(t) == m and np.array_equal(np.sort(t), np.arange(m))
    except Exception as e:
        rec["err"] = repr(e)[:80]; return rec
    gv = v[t]
    old = set(); fixed = set()
    for i in range(m):
        a, b = int(v[i]), int(v[(i + 1) % m])
        (old if real[i] else fixed).add((min(a, b), max(a, b)))
    new = set()
    for i in range(m):
        a, b = int(gv[i]), int(gv[(i + 1) % m]); new.add((min(a, b), max(a, b)))
    if not fixed <= new:
        rec["err"] = "fx"; return rec
    new -= fixed
    rem, add = sorted(old - new), sorted(new - old)
    co = int(sum(ln(a, b) for a, b in rem)) if rem else 0
    cn = int(sum(ln(a, b) for a, b in add)) if add else 0
    rec["d"] = cn - co; rec["x"] = len(add)
    if add and rec["d"] <= 50:
        with gzip.open(O / f"a{rec['j']}.txt.gz", "wt") as f:
            f.write(f"{rec['d']}\n" + " ".join(f"{a + 1}-{b + 1}" for a, b in rem) + "\n" + " ".join(f"{a + 1}-{b + 1}" for a, b in add) + "\n")
    if rec["d"] < 0:
        nt = apply(rem, add)
        if nt is None:
            rec["err"] = "apply"; RQ.append((rec["g"], rec["c"], m)); return rec
        nlv = L(nt)
        rec["gd"] = nlv - bl
        if nlv < bl:
            best, bl = nt, nlv; pos[best] = np.arange(N)
            for o_ in O.glob("t*.txt.gz"):
                o_.unlink()
            with gzip.open(O / f"t{R0 - bl}_j{S}.txt.gz", "wt") as f:
                f.write("\n".join(map(str, best + 1)) + "\n")
            log(f"+++ j{rec['j']} {R0 - bl}")
    return rec


while time.time() < t_end or run:
    while len(run) < W and time.time() < t_end - 400:
        run[j] = make(j); log(f"start j{j} n={run[j][2]['n']} f={run[j][2]['f']}"); j += 1
    for q in list(run):
        pr, d, rec, v, real, t0 = run[q]
        if time.time() > t_end and pr.poll() is None:
            pr.terminate()
            try:
                pr.wait(60)
            except Exception:
                pr.kill()
        if pr.poll() is None:
            continue
        del run[q]
        rec["sec"] = round(time.time() - t0); rec["rc"] = pr.returncode
        rec = finish(pr, d, rec, v, real)
        st["w"].append(rec); save()
        log(f"done j{q} n={rec['n']} d={rec.get('d')} x={rec.get('x')} g={R0 - bl} {rec.get('err', '')}")
        for f_ in d.iterdir():
            f_.unlink()
        d.rmdir()
    time.sleep(5)
save()
log(f"end {R0 - bl}")
