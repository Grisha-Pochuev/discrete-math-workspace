# Conditional B50 g24 candidate, NOT approved for dispatch.
from b50_resume_guard import preflight as _b50_preflight, validate_decoded_parent as _b50_validate, strict_decode as _b50_decode, validate_migration_bank as _b50_migration
_B50_PARENT = _b50_preflight(__file__)
import base64, gzip, hashlib, io, json, lzma, os, subprocess, sys, tarfile, time, urllib.request
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

S = int(sys.argv[1]); T = int(sys.argv[2]); W = int(os.environ.get("W", "4"))
_q = (os.environ.get("Q", "") + ",,,").split(",")
NP = int(_q[0] or 300); NK = int(_q[1] or 30); CY = int(_q[2] or 1)
FIXM = 200000; K = 50; MG = 2
t0 = time.time(); t_end = t0 + T; GD = int(t_end - int(os.environ.get("MS", "360"))); RS = int(os.environ.get("RS", "2400"))
D = Path("wd"); D.mkdir(exist_ok=True); O = Path("o"); O.mkdir(exist_ok=True)
P = Path("p"); Q = Path("q"); H = Path(__file__).with_name("h.bin")
_pt = os.environ.get("PERT", "0")
_NM = os.environ.get("NM", "0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19").split(","); _NG = os.environ.get("NG", "17" if S % 20 < 10 else "18")
_NW = os.environ.get("NW", "").split(",")
if not os.environ.get("HF", "") and _NG and str(S % 20) in _NM:
    _pt = _NG
    if str(S % 20) in _NW:
        import shutil; shutil.rmtree(P, ignore_errors=True)
SEAM = str(S % 20) in os.environ.get("SMS", ",".join(map(str, range(20)))).split(",") and Path(__file__).with_name(os.environ.get("SGF", "g24") + ".bin").exists()
if SEAM:
    _pt = os.environ.get("SGF", "g24")[1:]
    try:
        _sm = json.loads((P / "st.json").read_text()).get("sm", 0)
    except Exception:
        _sm = 0
    if not _sm:
        import shutil; shutil.rmtree(P, ignore_errors=True)
_DR = set()
for _x in os.environ.get("DRP", "").split(","):
    if _x and _x.split(":")[0] == str(S % 20):
        _DR.add(int(_x.split(":")[1])); (P / f"c{_x.split(':')[1]}.bin").unlink(missing_ok=True)
HF = os.environ.get("HF", "")
EXP = os.environ.get("EXP", "1") == "1" and not SEAM
os.environ.setdefault("GA_AB_CAP_POLICY", "stop" if EXP else "single")
SLK = int(os.environ.get("DS", "50")); QW = int(os.environ.get("QW", "50")); RW = float(os.environ.get("RW", "0.25"))
HD = bool(HF) and Path(__file__).with_name(HF).exists()
if HD:
    FIXM = int(os.environ.get("FX", "28000")); _pt = "h"
elif os.environ.get("FX"):
    FIXM = int(os.environ["FX"])
G = Path(__file__).with_name(HF) if HD else Path(__file__).with_name("g.bin" if _pt in ("", "0") else f"g{_pt}.bin")
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
    if _km and EXP:
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
st = json.loads(st_p.read_text()) if st_p.exists() else {"isl": {}}
_b50_validate(_B50_PARENT, P, lambda raw: _b50_decode(raw, NN, n, K, decoder=dec), NP, n, fl, adj_)
_b50_migration(P / "m.bin", dec, NN, n, K, fl, adj_)
M_in = (mig([Q / "m.bin"]) + mig([H])) if RI < 0 else (mig([P / "m.bin"]) + (mig([Q / "m.bin"]) if HD else []))
_ap = Path(__file__).with_name(f"a{_pt}_{RI}.bin")
AP = [t for t in mig([_ap if _ap.exists() else Path(__file__).with_name("a.bin")]) if fl(t) is not None]
AV = os.environ.get("AV", "1") == "1" and _ap.exists()
if HD:
    _lo = np.full(N, -1, np.int64); _lo[Lc] = np.arange(n)
    _bk = {}
    for _i in range(n):
        _bk[(min(_i, (_i + 1) % n), max(_i, (_i + 1) % n))] = 1
    _to = g["to"]; _ta = g["ta"].astype(np.int64); _tr = g["tr"].astype(np.int64); AP = []
    for _j in range(len(_to) - 1):
        _a = _lo[_ta[_to[_j]:_to[_j + 1]]]; _r = _lo[_tr[_to[_j]:_to[_j + 1]]]
        _adj = [[(_i - 1) % n, (_i + 1) % n] for _i in range(n)]
        for u_, v_ in _r.tolist():
            _adj[u_].remove(v_); _adj[v_].remove(u_)
        for u_, v_ in _a.tolist():
            _adj[u_].append(v_); _adj[v_].append(u_)
        _t = [0] * n; _p, _c = -1, 0
        for _i in range(n):
            _t[_i] = _c; _x = _adj[_c]; _nx = _x[0] if _x[0] != _p else _x[1]; _p, _c = _c, _nx
        _t = np.array(_t, np.int64)
        if len(np.unique(_t)) == n and fl(_t) is not None:
            AP.append(_t)
    del _bk
    NP = 1 + len(AP); AV = True
    log(f"hdr n={n} f={int(fx.sum())} t={len(AP)} " + " ".join(str(fl(t) - FL0) for t in AP[:3]))
log(f"in p={int(st_p.exists())} m={len(M_in)} a={len(AP)}")
rep = {"s": S, "ri": RI, "cy": CY, "v": 33, "abp": os.environ["GA_AB_CAP_POLICY"], "sm": int(SEAM), "hd": int(HD), "gain": 0, "isl": [], "imp": []}
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


EXL = [tuple(int(c) for c in z.split(":")) for z in os.environ.get("EXL", "1:0,1:1,2:0,2:1").split(",")]
EXS = None; EXR = False; EXI = {}
if EXP:
    M_in = []; AP = []; AV = False
    _pe = st.get("exp")
    if _pe and os.environ.get("EXN", "0") != "1" and all((P / f"c{k}.bin").exists() for k in range(W)):
        EXR = True; EXI = _pe; EXL = [tuple(z) for z in _pe["l"]]
    else:
        _ord = [int(os.environ["EK"])] if os.environ.get("EK") else ([0, 2, 1, 3] if S % 2 == 0 else [2, 0, 3, 1]) + list(range(4, W))
        for _k in _ord:
            _c = P / f"c{_k}.bin"
            if not _c.exists():
                continue
            _h, _ps = dec(_c.read_bytes())
            if not _h or _h[-1] == "done" or len(_ps) != NP or BH in set(eh(t) for t in _ps) or any(fl(t) is None for t in _ps):
                log(f"exp skip {_c.name}"); continue
            EXS = (_c.name, list(_h), _ps); break
        if EXS is None:
            log("exp nosrc"); EXP = False
        else:
            _pr = _pairs(len(EXS[2]))
            EXI = {"src": EXS[0], "l": [list(z) for z in EXL], "pairs": _pr, "h0": [tkey(t) for t in EXS[2]]}
            EXI["m0"] = em(EXS[2], EXS[1], EXI["h0"], _pr)
            log("exp m0 " + json.dumps(EXI["m0"]))
if EXP:
    rep["exp"] = {"src": EXI["src"], "l": EXI["l"], "res": int(EXR), "m0": EXI["m0"]}; rep["ts"] = {}
best_full = None


SW = str(RI) in os.environ.get("S2R", "").split(",")
AG = os.environ.get("AG", "1" if SW else "0") == "1"


def setup(k, fresh):
    I_ = W * S + k
    if EXP:
        e = {"tr": st["isl"].get(str(k), {}).get("tr", 0)}; xo, bs = EXL[k % len(EXL)]
        e["mode"] = "e%d%d" % (xo, bs); e["ix"] = "%d:%d" % (xo, bs)
        d = D / f"i{k}"; d.mkdir(exist_ok=True)
        for f_ in d.glob("imp*.txt"):
            f_.unlink()
        if EXR:
            hdr, ps = dec((P / f"c{k}.bin").read_bytes())
        else:
            hdr, ps = list(EXS[1]), [t.copy() for t in EXS[2]]
        hdr = list(hdr); hdr[2] = str(xo)
        wr(d / "in.txt", ps, hdr)
        env = dict(os.environ, GA_CKSEC=os.environ.get("CK", "1800"), GA_FIXM=str(FIXM), GA_FIXED_STAGE=str(xo), GA_XT=str(xo))
        for z in ("GA_LIVE", "GA_INJECT", "GA_START2", "GA_INJECT_AT_START", "GA_MAX_GENERATIONS", "GA_SEARCH_SECONDS"):
            env.pop(z, None)
        if bs:
            env["GA_INJECT"] = str(D / "r.txt"); env["GA_INJECT_AT_START"] = "1"
        seed = int(os.environ.get("ESEED", str(1000 * S + 7 * CY)))
        log(f"exp {k} x={xo} b={bs} src={EXI['src']} res={int(EXR)} seed={seed} g0={hdr[0]}")
        lf = open(O / f"l{k}_{e['tr']}.txt", "a")
        pr = subprocess.Popen([str(x), str(D / "g.inst"), str(d), str(NP), str(NK), str(seed), str(GD), str(REF), str(d / "in.txt")],
                              stdout=lf, stderr=subprocess.STDOUT, env=env)
        st["isl"][str(k)] = e
        return pr, lf
    e = st["isl"].get(str(k), {"tr": 0})
    rep_ = False
    if fresh:
        e = {"tr": e.get("tr", -1) + 1}
        rep_ = AG and any((P / f"c{j}.bin").exists() for j in range(W))
    tr = e["tr"]; mode = "a" if (I_ + tr) % 4 == 0 else "b"
    if rep_:
        mode = "b"
    if IXA:
        rep_ = False; mode = "x%d%d" % ixk(k); e["ix"] = "%d:%d" % ixk(k)
    e["mode"] = mode
    d = D / f"i{k}"; d.mkdir(exist_ok=True)
    for f_ in d.glob("imp*.txt"):
        f_.unlink()
    pf = "-"
    ck = P / f"c{k}.bin"
    if rep_:
        rep_ = False
        for j in range(W):
            ck_ = P / f"c{(k + tr + j) % W}.bin"
            if ck_.exists() and dec(ck_.read_bytes())[0][-1] != "done":
                ck = ck_; rep_ = True; break
        if rep_:
            e["src"] = ck.name; fresh = False
        else:
            mode = e["mode"] = "a" if (I_ + tr) % 4 == 0 else "b"
    if not fresh and ck.exists():
        hdr, ps = dec(ck.read_bytes())
        if hdr and hdr[-1] == "done":
            return setup(k, True)
        if hdr and int(hdr[8]) == len(ps) == NP and M_in:
            _cm = [t for t in M_in if not (IXA and ixk(k)[1] == 0 and eh(t) == BH)]
            try:
                j = ins_mig(ps, _cm, fl, limit=MG, slack=SLK)
            except Exception as ex_:
                log(f"mig {k}: {ex_}"); j = 0
            e["mig"] = j
        if hdr and IXA:
            hdr = list(hdr); hdr[2] = str(ixk(k)[0])
            if ixk(k)[1] == 1 and BH not in set(eh(t) for t in ps):
                v = [fl(t) for t in ps]
                w_ = int(np.argmax([x_ if x_ is not None else 1 << 62 for x_ in v])); ps[w_] = np.arange(n); e["bi"] = 1
        elif hdr and os.environ.get("S2", "1" if SW else "0") == "1" and hdr[1] == "1":
            hdr = list(hdr); hdr[1] = "2"; hdr[2] = "2"; hdr[3] = "0"; hdr[4] = "0"; hdr[5] = hdr[0]; e["s2"] = 1
        if hdr and not IXA and mode == "b" and (rep_ or str(k) in os.environ.get("BIK", "1").split(",")):
            v = [fl(t) for t in ps]
            if BH not in set(eh(t) for t in ps):
                w_ = int(np.argmax([x_ if x_ is not None else 1 << 62 for x_ in v])); ps[w_] = np.arange(n); e["bi"] = 1
        wr(d / "in.txt", ps, hdr); pf = str(d / "in.txt")
    elif HD:
        mode = e["mode"] = "v"
        rs = np.random.default_rng(1000 * I_ + tr + 100 * CY); pk = rs.permutation(len(AP))
        wr(d / "in.txt", [np.arange(n)] + [AP[j] for j in pk]); pf = str(d / "in.txt")
    elif AP and AV and k % 2 == 0:
        mode = e["mode"] = "v"
        wr(d / "in.txt", [np.arange(n)] + AP); pf = str(d / "in.txt")
    elif AP and not AV:
        mode = e["mode"] = "s"
        rs = np.random.default_rng(1000 * I_ + tr + 100 * CY)
        pick = rs.choice(len(AP), size=min(NP - 1, len(AP)), replace=False)
        wr(d / "in.txt", [np.arange(n)] + [AP[j] for j in pick]); pf = str(d / "in.txt")
    elif mode == "a" or (IXA and ixk(k)[1] == 1):
        pf = str(D / "r.txt")
    env = dict(os.environ, GA_CKSEC=os.environ.get("CK", "1800"), GA_LIVE=str(d / "live.txt"), GA_FIXM=str(FIXM))
    if IXA:
        env["GA_XT"] = str(ixk(k)[0])
        log(f"ix {k} x={ixk(k)[0]} b={ixk(k)[1]} mode={mode} bi={e.get('bi', 0)} mig={e.get('mig', 0)} pf={'r' if pf.endswith('r.txt') else ('in' if pf != '-' else '-')}")
    if mode == "s":
        env["GA_START2"] = "1"
    if mode == "b" and not HD:
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
                _a = full; _b = np.roll(_a, -1); _ek = np.minimum(_a, _b) * N + np.maximum(_a, _b)
                _r = R; _rb = np.roll(_r, -1); _rk = np.minimum(_r, _rb) * N + np.maximum(_r, _rb)
                _ad = np.setdiff1d(_ek, _rk); _rm = np.setdiff1d(_rk, _ek)
                (O / f"t{gn}.bin").write_bytes(lzma.compress(np.concatenate([[len(_rm)], _rm, _ad]).astype(np.int64).tobytes()))
                (O / "s.json").write_text(json.dumps(rep, separators=(",", ":")))



# ---- live exchange (hourly): export island bests to branch x<S>-<run>, import r85/x<pert>_<RI>.bin
LP = 999999999 if EXP else int(os.environ.get("LP", "999999999")); RP = os.environ.get("GITHUB_REPOSITORY", ""); RUN = os.environ.get("GITHUB_RUN_ID", "0")
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
            _, ps = rd(ck); out += sel_div(ps, fl, limit=3, slack=SLK, exclude=[np.arange(n)])
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

procs = {k: setup(k, k in _DR) for k in range(W)}
gone = set(); nl = 0; cmt = {}
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
        if time.time() < GD - RS and not EXP:
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
    if EXP:
        for k in range(W):
            ck = D / f"i{k}" / "ck.txt"
            try:
                mt = ck.stat().st_mtime
            except Exception:
                continue
            if mt != cmt.get(k):
                cmt[k] = mt
                try:
                    hdr_, ps_ = rd(ck)
                    if hdr_ and len(ps_) == NP:
                        r_ = em(ps_, hdr_, EXI["h0"], EXI["pairs"]); r_["t"] = int(time.time() - t0)
                        rep["ts"].setdefault(str(k), []).append(r_); log(f"ts {k} " + json.dumps(r_))
                        (O / "s.json").write_text(json.dumps(rep, separators=(",", ":")))
                except Exception as ex_:
                    log(f"ts {k}: {ex_}")
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
        seen = set(); neq = 0; hs = {}
        for j in o_:
            if np.isnan(v[j]) or v[j] - FL0 > 10:
                break
            hs.setdefault(eh(ps[j]), j)
        hs.pop(BH, None); r_["nd"] = len(hs); r_["ix"] = e.get("ix", "")
        if EXP:
            try:
                _m = em(ps, hdr, EXI["h0"], EXI["pairs"]); r_["ex"] = _m
                r_["dg"] = int(hdr[0]) - int(EXI["m0"]["g"]); r_["kids"] = r_["dg"] * NP * NK
            except Exception as ex_:
                log(f"em {k}: {ex_}")
        try:
            migr += sel_div(ps, fl, limit=3, slack=SLK, exclude=[np.arange(n)])
        except Exception as ex_:
            log(f"sel {k}: {ex_}")
    rep["isl"].append(r_)
    log(f"end {k} " + json.dumps({a: r_[a] for a in r_ if a not in ("q",)}))
if migr:
    (O / "m.bin").write_bytes(enc(migr))
if EXP:
    st["exp"] = EXI
if SEAM:
    st["sm"] = 1
(O / "st.json").write_text(json.dumps(st))
(O / "s.json").write_text(json.dumps(rep, separators=(",", ":")))
for f_ in O.glob("l*.txt"):
    with open(f_, "rb") as a, gzip.open(str(f_) + ".gz", "wb") as b:
        b.write(a.read())
    f_.unlink()
log(f"done gain={rep['gain']}")
