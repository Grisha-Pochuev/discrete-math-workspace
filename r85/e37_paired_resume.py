from b64_resume_guard import preflight, validate_geometry, finalize, supervise, validate_parents
ADMISSION = preflight(__file__)
import resource
import shutil
import base64, gzip, hashlib, io, json, lzma, os, subprocess, sys, tarfile, time, urllib.request
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

S = int(sys.argv[1]); T = int(sys.argv[2]); W = int(os.environ.get("W", "4"))
_q = (os.environ.get("Q", "") + ",,,").split(",")
NP = int(_q[0] or 300); NK = int(_q[1] or 30); CY = int(_q[2] or 1)
FIXM = 200000; K = 50; MG = 2
t0 = ADMISSION["started_epoch"]; t_end = t0 + T; GD = int(t_end - int(os.environ.get("MS", "360"))); RS = int(os.environ.get("RS", "2400"))
D = Path("wd"); D.mkdir(exist_ok=True); O = Path("o"); O.mkdir(exist_ok=True)
P = Path("p")
_pt = "25"
SEAM = True; HD = False; EXP = False
FIXM = 200000
SLK = 50; QW = 50; RW = 0.25
os.environ["GA_AB_CAP_POLICY"] = "single"
G = Path(__file__).with_name("g25.bin")
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
validate_geometry(ADMISSION, g, X, R, R0, S)
pos = np.empty(N, np.int64); pos[R] = np.arange(N)
if HD:
    RI = 0; ids = g["i"].astype(np.int64)
elif "rc" in g.files:
    _rot = g["rc"].astype(np.float64); _k = int(g["rk"]); RI = S % _k
    if str(S % 20) in os.environ.get("RO", "").split(","):
        RI = (RI + 20) % _k
    _P = X @ _rot.T; _out = []
    def _rec(idx, k):
        if k == 1: _out.append(np.sort(idx)); return
        k1 = k // 2; Q_ = _P[idx]; ax = int(np.argmax(Q_.max(0) - Q_.min(0)))
        o_ = idx[np.argsort(Q_[:, ax], kind="stable")]; m_ = len(idx) * k1 // k
        _rec(o_[:m_], k1); _rec(o_[m_:], k - k1)
    _rec(np.arange(N, dtype=np.int64), _k); ids = _out[RI]; del _P, _out
elif "o" in g.files:
    _o = g["o"].astype(np.int64); RI = S % (len(_o) - 1)
    ids = g["i"][_o[RI]:_o[RI + 1]].astype(np.int64)
else:
    RI = -1; ids = g["i"].astype(np.int64)
Lc = ids[np.argsort(pos[ids])]; n = len(Lc); pc = pos[Lc]
fx = ((np.roll(pc, -1) - pc) % N) != 1
if HD:
    _dk = g["dk"].astype(np.int64); _dk = np.sort(np.minimum(_dk[:, 0], _dk[:, 1]) * N + np.maximum(_dk[:, 0], _dk[:, 1]))
    fx = ~np.isin(np.minimum(Lc, np.roll(Lc, -1)) * N + np.maximum(Lc, np.roll(Lc, -1)), _dk)
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
KP = [('cross.cpp', 'void TCross::BackToPa1( TIndi& tKid )\n{\n', 'void TCross::BackToPa1( TIndi& tKid )\n{\n  fNumOfSPL = 0;\n'), ('cross.cpp', 'void TCross::GoToBest( TIndi& tKid )\n{\n', 'void TCross::GoToBest( TIndi& tKid )\n{\n  fNumOfSPL = 0;\n'), ('env.cpp', '  }\n  this->GetEdgeFreq();\n  fInject = getenv( "GA_INJECT" );\n  fInjected = 0;\n  for( int i = 0; i < fNumOfPop; ++i ) if( tCurPop[i].fEvaluationValue == fRefVal ) fInjected = 1;\n  fStagAvg = getenv( "GA_STAG" ) ? atoi( getenv( "GA_STAG" ) ) : 1;\n  { double a = 0; for( int i = 0; i < fNumOfPop; ++i ) a += tCurPop[i].fEvaluationValue; fBestAvg = resumed ? a / fNumOfPop : 1e300; }\n  fBestSeen = 2147483647;\n', '  }\n  this->GetEdgeFreq();\n  fInject = getenv( "GA_INJECT" );\n  fInjected = ReferencePresent() ? 1 : 0;\n  printf( "ref_present %d\\n", fInjected );\n  /* Optional controlled experiment; the ordinary production path is unchanged. */\n  fFixedStage = getenv( "GA_FIXED_STAGE" ) ? atoi( getenv( "GA_FIXED_STAGE" ) ) : 0;\n  if( fFixedStage < 0 || fFixedStage > 2 ){ fprintf( stderr, "invalid fixed stage\\n" ); exit( 4 ); }\n  fExperimentStartGen = fCurNumOfGen;\n  fExperimentGenerations = getenv( "GA_MAX_GENERATIONS" ) ? atoi( getenv( "GA_MAX_GENERATIONS" ) ) : 0;\n  if( fFixedStage ){\n    fStage = fFixedStage; fFlagC[1] = fFixedStage;\n    fStagBest = 0; fMaxStagBest = 0; fCurNumOfGen1 = fCurNumOfGen;\n    if( getenv( "GA_INJECT_AT_START" ) && atoi( getenv( "GA_INJECT_AT_START" ) ) ){\n      if( !fInject ){ fprintf( stderr, "missing reference for injection\\n" ); exit( 4 ); }\n      if( !fInjected ) this->DoInject();\n    }\n    /* Prevent an automatic later injection in the control groups. */\n    fInject = NULL;\n    if( getenv( "GA_SEARCH_SECONDS" ) ){\n      long seconds = atol( getenv( "GA_SEARCH_SECONDS" ) );\n      if( seconds <= 0 ){ fprintf( stderr, "invalid search budget\\n" ); exit( 4 ); }\n      long limit = (long)time( NULL ) + seconds;\n      if( limit < fDeadline ) fDeadline = limit;\n    }\n    printf( "experiment stage=%d initial_injection=%d start_gen=%d max_generations=%d\\n",\n            fFixedStage, getenv( "GA_INJECT_AT_START" ) ? atoi( getenv( "GA_INJECT_AT_START" ) ) : 0,\n            fExperimentStartGen, fExperimentGenerations );\n  }\n  fStagAvg = getenv( "GA_STAG" ) ? atoi( getenv( "GA_STAG" ) ) : 1;\n  { double a = 0; for( int i = 0; i < fNumOfPop; ++i ) a += tCurPop[i].fEvaluationValue; fBestAvg = resumed ? a / fNumOfPop : 1e300; }\n  fBestSeen = 2147483647;\n'), ('env.cpp', '} \n\n/* See Section 2.2 */\nvoid TEnvironment::DoInject()\n{\n  /* late injection of the reference piece: replace the worst member, recompute edge frequencies */\n', '} \n\n/* See Section 2.2 */\nbool TEnvironment::ReferencePresent()\n{\n  if( !fInject ) return false;\n  FILE* fp = fopen( fInject, "r" );\n  if( !fp ) return false;\n  TIndi reference; reference.Define( fEvaluator->Ncity );\n  bool read = fEvaluator->ReadFrom( fp, reference );\n  fclose( fp );\n  if( !read ) return false;\n  for( int i = 0; i < fNumOfPop; ++i )\n    if( tCurPop[i] == reference ) return true;\n  return false;\n}\n\nvoid TEnvironment::DoInject()\n{\n  /* late injection of the reference piece: replace the worst member, recompute edge frequencies */\n'), ('env.cpp', '\nbool TEnvironment::TerminationCondition()\n{\n  if ( fAverageValue - fBestValue < 0.001 ){\n    if( fInject && !fInjected ){ this->DoInject(); fStage = 2; fFlagC[1] = 2; fStagBest = 0; fMaxStagBest = 0; fCurNumOfGen1 = fCurNumOfGen; return false; }\n    return true;\n', '\nbool TEnvironment::TerminationCondition()\n{\n  if( fFixedStage )\n    return fExperimentGenerations > 0 &&\n           fCurNumOfGen - fExperimentStartGen >= fExperimentGenerations;\n  if ( fAverageValue - fBestValue < 0.001 ){\n    if( fInject && !fInjected ){ this->DoInject(); fStage = 2; fFlagC[1] = 2; fStagBest = 0; fMaxStagBest = 0; fCurNumOfGen1 = fCurNumOfGen; return false; }\n    return true;\n'), ('env.h', '  char* fInject;\n  int fInjected;\n  void DoInject();\n\n\n  TEvaluator* fEvaluator;                /* Distance of the edges */\n', '  char* fInject;\n  int fInjected;\n  void DoInject();\n  bool ReferencePresent();\n  int fFixedStage;\n  int fExperimentStartGen;\n  int fExperimentGenerations;\n\n\n  TEvaluator* fEvaluator;                /* Distance of the edges */\n')]
x = D / "x"
if not x.exists():
    sd = D / "src"; sd.mkdir(exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(lzma.decompress(g["s"].tobytes()))) as tf:
        tf.extractall(sd)
    cx = os.environ.get("CXX", "g++ -O3 -march=native").split()
    _ec = sd / "env.cpp"; _et = _ec.read_text(); _o = "fFlagC[ 1 ] = 1;"
    if _et.count(_o) == 1:
        _ec.write_text(_et.replace(_o, 'fFlagC[ 1 ] = getenv( "GA_XT" ) ? atoi( getenv( "GA_XT" ) ) : 1;'))
    else:
        log("xt patch miss")
    _km = 0
    for _fn, _o3, _n3 in KP:
        _fp = sd / _fn; _tx = _fp.read_text()
        if _tx.count(_o3) == 1:
            _fp.write_text(_tx.replace(_o3, _n3))
        else:
            _km += 1
    _ec = sd / "env.cpp"; _et = _ec.read_text()
    _o4 = 'printf( "g %d s %d b %d a %.1f t %ld\\n", fCurNumOfGen, fStage, fBestValue - fRefVal, fAverageValue - fRefVal,\n            (long)time( NULL ) - fT0 );'
    if _et.count(_o4) == 1:
        _ec.write_text(_et.replace(_o4, 'printf( "g %d s %d b %d a %.1f t %ld x %d\\n", fCurNumOfGen, fStage, fBestValue - fRefVal, fAverageValue - fRefVal,\n            (long)time( NULL ) - fT0, fFlagC[ 1 ] );'))
    else:
        _km += 1
    log(f"kp miss={_km}")
    if _km:
        raise SystemExit("kp")
    from ab_cap_patch import apply_ab_cap_patch
    apply_ab_cap_patch(sd)
    log(f"abcap patch ok policy={os.environ['GA_AB_CAP_POLICY']}")
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


def eh(t):
    return hashlib.sha1(ekeys(t).tobytes()).hexdigest()


BH = eh(np.arange(n))


# ---- structural selection (identity by undirected edge set; invariant to shift/reversal)
def adj_(t):
    t = np.asarray(t, np.int64); m = len(t)
    if m < 3 or t.min() < 0 or t.max() >= m or not np.all(np.bincount(t, minlength=m) == 1):
        raise ValueError("perm")
    a = np.empty((m, 2), "<u4"); b_, a_ = np.roll(t, 1), np.roll(t, -1)
    a[t, 0] = np.minimum(b_, a_); a[t, 1] = np.maximum(b_, a_)
    return a


def tkey(t):
    return hashlib.sha256(adj_(t).tobytes()).hexdigest()


def edist(a, b):
    c2 = sum(int(np.count_nonzero(a[:, i] == b[:, j])) for i in range(2) for j in range(2))
    return len(a) - c2 // 2


def sel_div(ts, cost, limit=3, slack=50, exclude=(), ref=None):
    if limit <= 0:
        return []
    seen = {tkey(t) for t in exclude}; pool = []
    for o_, t in enumerate(ts):
        v_ = cost(t)
        if v_ is None:
            continue
        a = adj_(t); h_ = hashlib.sha256(a.tobytes()).hexdigest()
        if h_ in seen:
            continue
        seen.add(h_); pool.append((np.asarray(t), int(v_), h_, a, o_))
    if not pool:
        return []
    bv = min(c[1] for c in pool); pool = [c for c in pool if c[1] <= bv + slack]
    anc = [adj_(ref)] if ref is not None else []
    first = max((c for c in pool if c[1] == bv), key=lambda c: (edist(c[3], anc[0]) if anc else 0, -c[4]))
    ch = [first]; anc.append(first[3]); pool = [c for c in pool if c[2] != first[2]]
    while pool and len(ch) < limit:
        c = max(pool, key=lambda x_: (min(edist(x_[3], a) for a in anc), -x_[1], -x_[4]))
        ch.append(c); anc.append(c[3]); pool = [x_ for x_ in pool if x_[2] != c[2]]
    return [c[0] for c in ch]


def ins_mig(pop, migs, cost, limit=2, slack=50):
    vals = [cost(t) for t in pop]
    if not vals or any(v_ is None for v_ in vals):
        return 0
    cands = sel_div(migs, cost, limit=limit, slack=slack, exclude=pop)
    slots = sorted(range(len(vals)), key=lambda i: (vals[i], i), reverse=True); used = 0
    for t in cands:
        v_ = cost(t)
        if used >= len(slots) or v_ is None or v_ > vals[slots[used]]:
            continue
        pop[slots[used]] = np.asarray(t).copy(); vals[slots[used]] = v_; used += 1
    return used
_ix = "0" if SEAM else os.environ.get("IX", "1:0,1:1,2:0,2:1")
IXA = _ix not in ("", "0")
IXL = [tuple(int(c) for c in z.split(":")) for z in _ix.split(",")] if IXA else []


def ixk(k):
    return IXL[k % len(IXL)] if IXA else None


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
st = {"isl": {}}
PARENTS = validate_parents(ADMISSION, P, NN, n, fkey, fl, REF, Lc)
M_in = []; AP = []; AV = False
log("source-bound RNG continuation: preserved population/stage/counters; no donors, exchanges or restart")
rep = {"s": S, "ri": RI, "cy": CY, "v": 62, "abp": "single", "sm": 1, "hd": 0, "gain": 0, "isl": [], "imp": [], "design": ADMISSION["design_id"], "source_kind": "rng-population-continuation", "parent_run": ADMISSION["parent_run"], "parent_identity": ADMISSION["parent"]["identity"], "job_binding": ADMISSION["job"], "child_exits": []}
BHK = tkey(np.arange(n))


def _pairs(m, c=40):
    r = np.random.default_rng(12345); out = set()
    while len(out) < min(c, m * (m - 1) // 2):
        i, j = sorted(r.choice(m, 2, replace=False).tolist()); out.add((i, j))
    return sorted(out)


def em(ps, hdr, H0=None, pairs=None):
    v = np.array([np.nan if (z := fl(t)) is None else z for t in ps], dtype=float)
    vb = np.nanmin(v); ks = [tkey(t) for t in ps]
    win = {ks[i] for i in range(len(ps)) if v[i] <= vb + QW}; win.discard(BHK)
    r = {"g": int(hdr[0]), "st": int(hdr[1]), "x": int(hdr[2]), "tag": hdr[-1], "b": float(vb - FL0), "a": float(np.nanmean(v) - FL0),
         "un": len(set(ks)), "uq": len(win), "nd": len({ks[i] for i in range(len(ps)) if v[i] - FL0 <= 10} - {BHK}), "bp": int(BHK in ks)}
    wr_ = {ks[i] for i in range(len(ps)) if v[i] <= vb + RW * (np.nanmean(v) - vb)}; wr_.discard(BHK); r["uqr"] = len(wr_)
    if H0 is not None:
        r["nq"] = len(win - set(H0)); r["nqr"] = len(wr_ - set(H0))
    if pairs:
        ca = {}; dl = []
        for i, j in pairs:
            if i < len(ps) and j < len(ps):
                for z in (i, j):
                    if z not in ca:
                        ca[z] = adj_(ps[z])
                dl.append(edist(ca[i], ca[j]))
        r["md"] = float(np.median(dl)) if dl else -1.0
    return r


best_full = None

def setup(k):
    # Exact same ordered parent population. Fresh RNG stream, NOT RNG-state resume.
    e = {"tr": 0, "mode": "a" if k == 0 else "b"}
    d = D / f"i{k}"; d.mkdir()
    hdr, ps, evidence = PARENTS[k]
    wr(d / "in.txt", ps, hdr)
    read_h, read_ps = rd(d / "in.txt")
    if read_h != hdr or len(read_ps) != len(ps) or any(not np.array_equal(a,b) for a,b in zip(read_ps,ps)):
        raise ValueError("native input readback mismatch")
    pf = str(d / "in.txt")
    e["parent"] = evidence
    e["rng_continuation"] = True
    env = dict(os.environ, GA_CKSEC="1800", GA_FIXM=str(FIXM))
    for key in list(env):
        if key.startswith("GA_"):
            env.pop(key)
    env.update(GA_CKSEC="1800", GA_FIXM=str(FIXM), GA_AB_CAP_POLICY="single")
    if k != 0:
        env["GA_INJECT"] = str(D / "r.txt")
    seed = ADMISSION["job"]["seeds"][k]
    e["seed"] = seed
    log(f"resume {k} seed={seed} mode={e['mode']} geometry={RI} g={hdr[0]} stage={hdr[1]}")
    lf = open(O / f"l{k}_0.txt", "x")
    try:
        pr = subprocess.Popen([str(x), str(D / "g.inst"), str(d), str(NP), str(NK), str(seed), str(GD), str(REF), pf], stdout=lf, stderr=subprocess.STDOUT, env=env)
    except Exception:
        lf.close()
        raise
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
                _a = full; _b = np.roll(_a, -1); _ek = np.minimum(_a, _b) * N + np.maximum(_a, _b)
                _r = R; _rb = np.roll(_r, -1); _rk = np.minimum(_r, _rb) * N + np.maximum(_r, _rb)
                _ad = np.setdiff1d(_ek, _rk); _rm = np.setdiff1d(_rk, _ek)
                (O / f"t{gn}.bin").write_bytes(lzma.compress(np.concatenate([[len(_rm)], _rm, _ad]).astype(np.int64).tobytes()))
                (O / "s.json").write_text(json.dumps(rep, separators=(",", ":")))



# No inter-island or cross-job exchanges and no automatic new trials.
require_budget = GD - time.time()
if require_budget < 600: raise SystemExit("insufficient search admission margin")
cpu0 = resource.getrusage(resource.RUSAGE_CHILDREN)
rep["prepared_seconds"] = time.time()-t0
search_started=time.time()
def save_exits():
    (O / "child_exits.json").write_text(json.dumps(rep["child_exits"]))
procs = supervise(setup,W,chk_imp,rep,GD+30,on_exit=save_exits)
# Errors never skip terminal, per-island harvest or falsely certify completeness.
migr = []
for k in range(W):
    if not rep["harvest_allowed"]: break
    try:
        e = st["isl"].get(str(k), {"mode":"unlaunched","tr":0})
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
            seen = set(); neq = 0; hs = {}
            for j in o_:
                if np.isnan(v[j]) or v[j] - FL0 > 10:
                    break
                hs.setdefault(eh(ps[j]), j)
            hs.pop(BH, None); r_["nd"] = len(hs); r_["ix"] = e.get("ix", "")
            try:
                migr += sel_div(ps, fl, limit=3, slack=SLK, exclude=[np.arange(n)])
            except Exception as ex_:
                log(f"sel {k}: {ex_}")
        rep["isl"].append(r_)
        log(f"end {k} " + json.dumps({a: r_[a] for a in r_ if a not in ("q",)}))
    except Exception as exc:
        rep["runtime_errors"].append({"where":"harvest "+str(k),"error":repr(exc)})
        ck=D/f"i{k}"/"ck.txt"
        if ck.is_file():
            try: shutil.copyfile(ck,O/f"salvage_ck{k}.txt")
            except Exception as salvage_exc:
                rep["runtime_errors"].append({"where":"salvage "+str(k),"error":repr(salvage_exc)})
if migr:
    (O / "m.bin").write_bytes(enc(migr))
if SEAM:
    st["sm"] = 1
(O / "st.json").write_text(json.dumps(st))
(O / "s.json").write_text(json.dumps(rep, separators=(",", ":")))
for f_ in O.glob("l*.txt"):
    with open(f_, "rb") as a, gzip.open(str(f_) + ".gz", "wb") as b:
        b.write(a.read())
    f_.unlink()
log(f"done gain={rep['gain']}")

cpu1=resource.getrusage(resource.RUSAGE_CHILDREN)
rep["solver_child_cpu_seconds"]=(cpu1.ru_utime+cpu1.ru_stime)-(cpu0.ru_utime+cpu0.ru_stime)
rep["solver_wall_seconds"]=time.time()-search_started
rep["runtime_identity"]=ADMISSION["runtime_identity"]
(O / "s.json").write_text(json.dumps(rep))
finalize(O, rep, NP, W)
