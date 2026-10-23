import base64, gzip, hashlib, json, os, subprocess, sys, tarfile, time, urllib.request
from pathlib import Path

import numpy as np

S = int(sys.argv[1]); T = int(sys.argv[2]); W = int(os.environ.get("W", "4"))
D = Path("wd"); D.mkdir(exist_ok=True); O = Path("o"); O.mkdir(exist_ok=True)
B = base64.b64decode("aHR0cHM6Ly93d3cubWF0aC51d2F0ZXJsb28uY2EvdHNwL3N0YXIvZGF0YS9nYWlhMjA3OTQ3MQ==").decode()
I = {"a": (B + ".xyz.txt.gz", "0a613505e22d15f67372824568bce53255b088d677889bc9990299afea5735b4"),
     "b": (B + "_tour.txt.gz", "ab3c6fa0ff96eae12b9b63c8f8654b839e90621f2acc866c18cdf54720b4e852")}
K = [base64.b64decode(x).decode() for x in (
    "aHR0cDovL3dlYmhvdGVsNC5ydWMuZGsvfmtlbGQvcmVzZWFyY2gvTEtILTMvTEtILTMuMC4xMy50Z3o=",
    "aHR0cHM6Ly9naXRodWIuY29tL2NlcmViaXMvTEtIMy5naXQ=")]
R0 = 288843524
P = ["3000", "4000", "5000", "6000", "8000", "10000", "5000 K-MEANS", "8000 K-MEANS BORDERS",
     "5000 KARP", "8000 KARP BORDERS", "2500", "12000"]
t_end = time.time() + T


def log(m):
    print(time.strftime("%H:%M:%S ") + m, flush=True)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


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
raw = [l.strip() for l in gzip.open(D / "a", "rt") if l.strip()]
X = np.array([[float(v) for v in l.split()] for l in raw]); N = len(X)
R = np.loadtxt(gzip.open(D / "b"), dtype=np.int64)


def L(t):
    assert len(t) == N and np.array_equal(np.sort(t), np.arange(1, N + 1))
    q = X[t - 1]
    return int(np.floor(np.sqrt(((q - np.roll(q, -1, 0)) ** 2).sum(1)) + 0.5).sum())


def wt(t, p):
    p.write_text(f"TYPE : TOUR\nDIMENSION : {N}\nTOUR_SECTION\n" + "\n".join(map(str, t)) + "\n-1\nEOF\n")


def rt(p):
    s = p.read_text().split("TOUR_SECTION")[1].split()
    t = []
    for v in s:
        v = int(v)
        if v == -1:
            break
        t.append(v)
    return np.array(t, dtype=np.int64)


assert L(R) == R0
with open(D / "g.tsp", "w") as f:
    f.write(f"TYPE : TSP\nDIMENSION : {N}\nEDGE_WEIGHT_TYPE : EUC_3D\nNODE_COORD_SECTION\n")
    for i, l in enumerate(raw):
        f.write(f"{i + 1} {l}\n")
    f.write("EOF\n")

x = D / "x"
if not x.exists():
    src = None
    try:
        with urllib.request.urlopen(K[0], timeout=20) as r_, open(D / "k.tgz", "wb") as f_:
            f_.write(r_.read())
        with tarfile.open(D / "k.tgz") as tf:
            tf.extractall(D)
        src = next(D.glob("LKH-3*/SRC"))
    except Exception as e:
        log(f"k0: {e}")
        subprocess.run(["git", "clone", "-q", "--depth", "1", K[1], str(D / "kg")], check=True)
        src = D / "kg" / "SRC"
    subprocess.run(["gcc", "-O3", "-march=native", "-fcommon", "-w", "-I", str(src / "INCLUDE"), "-o", str(x),
                    *map(str, src.glob("*.c")), "-lm"], check=True)
log("ok")

best, bl = R.copy(), R0
if int(os.environ.get("PERT", "0")):  # fire test: start from a deliberately worsened tour
    rng = np.random.default_rng(S)
    for _ in range(int(os.environ["PERT"])):
        a = int(rng.integers(0, 300000)); k = int(rng.integers(5, 40)); best[a:a + k] = best[a:a + k][::-1].copy()
    bl = L(best); R0 = bl; log("pert")
wt(best, D / "best.tour")
st = {"s": S, "jobs": []}
run, j = {}, 0
hv, pv, mt = {}, {}, {}


def harvest(q, d):
    """Verify the full tour LKH writes to TOUR_FILE after each global improvement."""
    global best, bl
    p = d / "o.tour"
    if not p.exists():
        return
    m = p.stat().st_mtime
    if mt.get(q) == m:
        return
    try:
        t = rt(p); v = L(t)
    except Exception as e:
        log(f"j{q} unreadable o.tour (maybe mid-write): {e!r}"); return
    mt[q] = m
    if pv.get(q) is None or v < pv[q]:
        pv[q] = v
        log(f"j{q} d={v - R0}")
        if v < R0:
            with gzip.open(O / f"t{v}_j{q}.txt.gz", "wt") as f:
                f.write("\n".join(map(str, t)) + "\n")
            for o_ in O.glob(f"t*_j{q}.txt.gz"):
                if o_.name != f"t{v}_j{q}.txt.gz":
                    o_.unlink()
    if v < bl:
        best, bl = t, v; wt(best, D / "best.tour")
        st["gain"] = R0 - bl
        (O / "s.json").write_text(json.dumps(st, indent=1))
        log(f"+++ j{q} {R0 - v}")

while time.time() < t_end or run:
    while len(run) < W and time.time() < t_end - 900:
        g = S * 97 + j
        r = P[(S * W + j) % len(P)]
        d = D / f"j{j}"; d.mkdir(exist_ok=True)
        (d / "s.tour").write_text((D / "best.tour").read_text())
        (d / "p").write_text("\n".join([
            f"PROBLEM_FILE = {D / 'g.tsp'}", f"INITIAL_TOUR_FILE = {d / 's.tour'}",
            f"SUBPROBLEM_TOUR_FILE = {d / 's.tour'}", f"SUBPROBLEM_SIZE = {r}",
            "MOVE_TYPE = 5", "MAX_CANDIDATES = 6",
            f"MAX_TRIALS = {os.environ.get('MT', '3000')}", "STOP_AT_OPTIMUM = NO", "RUNS = 1",
            f"SEED = {1 + g}", f"TIME_LIMIT = {max(600, int(t_end - time.time()))}",
            f"TOUR_FILE = {d / 'o.tour'}", "TRACE_LEVEL = 1", ""]))
        pr = subprocess.Popen([str(x), str(d / "p")], stdout=open(d / "l", "w"), stderr=subprocess.STDOUT)
        run[j] = (pr, d, r, time.time()); log(f"start j{j} {r.split()[0]}"); j += 1
    for q in list(run):
        pr, d, r, t0 = run[q]
        if time.time() > t_end and pr.poll() is None:
            pr.terminate()
            try:
                pr.wait(60)
            except Exception:
                pr.kill()
        done = pr.poll() is not None
        if done or time.time() - hv.get(q, 0) > 300:
            hv[q] = time.time(); harvest(q, d)
        if not done:
            continue
        del run[q]
        nsub = sum(1 for l in open(d / "l") if l.startswith("Subproblem "))
        nimp = sum(1 for l in open(d / "l") if l.startswith("*** "))
        st["jobs"].append({"j": q, "r": r, "d": None if pv.get(q) is None else pv[q] - R0, "sec": round(time.time() - t0), "sub": nsub,
                           "imp_lines": nimp, "rc": pr.returncode})
        st["gain"] = R0 - bl
        (O / "s.json").write_text(json.dumps(st, indent=1))
        log(f"done j{q} d={None if pv.get(q) is None else pv[q] - R0} g={R0 - bl} sub={nsub} imp={nimp} rc={pr.returncode}")
    time.sleep(20)
st["gain"] = R0 - bl
(O / "s.json").write_text(json.dumps(st, indent=1))
log(f"end {R0 - bl}")
