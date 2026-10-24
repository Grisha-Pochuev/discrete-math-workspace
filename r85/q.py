import base64, gzip, hashlib, io, json, os, subprocess, sys, tarfile, time, urllib.request
from pathlib import Path

import numpy as np

S = int(sys.argv[1]); T = int(sys.argv[2]); W = int(os.environ.get("W", "4"))
Q = os.environ.get("Q", "5000,10000,20000").split(",")
TL = {5000: 720, 10000: 1200, 20000: 2400, 30000: 3000, 50000: 3300, 100000: 6600}
RN = int(os.environ.get("RN", "4"))
D = Path("wd"); D.mkdir(exist_ok=True); O = Path("o"); O.mkdir(exist_ok=True)
Z = Path(__file__).with_name("u.bin")
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
zm, zh = z["m"].astype(np.int64), z["h"].astype(np.int64)
rng = np.random.default_rng(7919 * S + 17)
best, bl = R.copy(), R0
PF = float(os.environ.get("PF", "0"))
segs = []
for q in rng.permutation(len(zm)):
    if rng.random() > PF:
        continue
    p_, r_ = int(zm[q, 0]), int(zm[q, 1])
    a1, b1 = p_ + 1, r_
    if b1 - a1 + 1 > N // 2:
        a1, b1 = r_ + 1, p_ + N
    segs.append((a1, b1, int(q)))
segs.sort()
acc, last = [], -10
for a1, b1, q in segs:
    if a1 >= last + 2 and (not acc or b1 < acc[0][0] + N - 1):
        acc.append((a1, b1, q)); last = b1
for a1, b1, q in acc:
    ix = np.arange(a1, b1 + 1) % N
    best[ix] = best[ix[::-1]]
bl = L(best); assert bl == R0, (bl, R0)
pos = np.empty(N, np.int64); pos[best] = np.arange(N)
PN = np.zeros(N, bool)
for a1, b1, q in acc:
    PN[R[np.array([a1 - 1, b1, b1 + 1]) % N]] = True
log(f"p {len(acc)}")
st = {"s": S, "w": [], "gain": 0, "P": sorted(q for _, _, q in acc)}
run, j = {}, 0


def save():
    st["gain"] = R0 - bl
    (O / "s.json").write_text(json.dumps(st, separators=(",", ":")))


RQ = []


def make(j):
    if RQ:
        g, c, m = RQ.pop()
    elif rng.random() < float(os.environ.get("HF", "1")):
        g = int(rng.choice(len(zh), p=zh[:, 3] / zh[:, 3].sum()))
        c = int(R[int(rng.integers(zh[g, 0], zh[g, 1]))]); m = int(Q[(S + j) % len(Q)])
    else:
        g = 1000 + int(rng.integers(len(zm)))
        c = int(R[(int(zm[g - 1000, 0]) + int(rng.integers(0, 2))) % N]); m = int(Q[(S + j) % len(Q)])
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
    tl = max(60, min(tl, int(t_end - time.time()) - 90))
    ta = max(30, tl // (RN + 1))
    com = ["MOVE_TYPE = 5", "STOP_AT_OPTIMUM = NO", "RUNS = 1", "TRACE_LEVEL = 1"]
    cmd = []
    for k in range(RN):
        (d / f"pa{k}").write_text("\n".join([f"PROBLEM_FILE = {d / 'g.p'}", "MAX_CANDIDATES = 6", "CANDIDATE_SET_TYPE = POPMUSIC",
            "INITIAL_PERIOD = 1000", f"MAX_TRIALS = {int(os.environ.get('MT', '0')) or m}",
            f"SEED = {1 + S * 1009 + j * 7 + k}", f"TIME_LIMIT = {ta}", f"OUTPUT_TOUR_FILE = {d / f'f{k}.tour'}", *com, ""]))
        cmd.append(f"{x} {d / f'pa{k}'}")
    (d / "p").write_text("\n".join([f"PROBLEM_FILE = {d / 'g.p'}", f"INITIAL_TOUR_FILE = {d / 's.tour'}",
        "MAX_CANDIDATES = 0", "SUBGRADIENT = NO", f"MERGE_TOUR_FILE = {d / 's.tour'}",
        *[f"MERGE_TOUR_FILE = {d / f'f{k}.tour'}" for k in range(RN)],
        f"MAX_TRIALS = {max(100, m // 10)}", f"SEED = {7 + S * 1009 + j}", f"TIME_LIMIT = {ta}",
        f"OUTPUT_TOUR_FILE = {d / 'o.tour'}", *com, ""]))
    cmd.append(f"{x} {d / 'p'}")
    pr = subprocess.Popen(["sh", "-c", "; ".join(cmd)], stdout=open(d / "l", "w"), stderr=subprocess.STDOUT, start_new_session=True)
    return pr, d, {"j": j, "c": c, "g": g, "n": m, "f": len(fx), "pz": int(PN[v].sum())}, v, real, time.time()


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
    c0 = int(ln(v, np.roll(v, -1)).sum()); fd = []; fx = []
    ow = set((min(int(v[i]), int(v[(i + 1) % m])), max(int(v[i]), int(v[(i + 1) % m]))) for i in range(m))
    for k in range(RN):
        try:
            tk = v[rt(d / f"f{k}.tour")]; dk = int(ln(tk, np.roll(tk, -1)).sum()) - c0
            nw = set((min(int(tk[i]), int(tk[(i + 1) % m])), max(int(tk[i]), int(tk[(i + 1) % m]))) for i in range(m))
            rk, ak = sorted(ow - nw), sorted(nw - ow)
            fd.append(dk); fx.append(len(ak))
            if ak and dk <= 50:
                with gzip.open(O / f"a{rec['j']}_{k}.txt.gz", "wt") as f:
                    f.write(f"{dk}\n" + " ".join(f"{a + 1}-{b + 1}" for a, b in rk) + "\n" + " ".join(f"{a + 1}-{b + 1}" for a, b in ak) + "\n")
        except Exception:
            fd.append(None); fx.append(None)
    rec["fd"] = fd; rec["fx"] = fx
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
            try:
                os.killpg(pr.pid, 15)
            except Exception:
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
