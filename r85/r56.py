"""Paired regression test of two instance-selection strategies."""
from pathlib import Path
from hashlib import sha256
import os, sys
def replace_once(s, a, b):
    if s.count(a) != 1:
        raise RuntimeError("Unexpected dependency version")
    return s.replace(a, b)
p = Path(__file__).with_name("e43.py")
raw = p.read_bytes()
if sha256(raw).hexdigest() != "015c1bc98a5d1fe7883b5d02562bb25593db8135888b3fb1b32699813e11333b":
    raise RuntimeError("Dependency checksum mismatch")
arm = os.environ.get("R56_ARM")
if arm not in ("c","t") or len(sys.argv)!=3 or sys.argv[1]!="129":
    raise RuntimeError("Invalid comparison")
prep = os.environ.get("R56_PREP") == "1"
if prep != bool(os.environ.get("LOCAL")) or (not prep and sys.argv[2]!="20700"):
    raise RuntimeError("Wrong comparison budget or input")
os.environ.update(W="4",Q="100,30,1",LP="999999999",GH_TOKEN="")
s=raw.decode()
s=replace_once(s,"tf.extractall(sd)",'tf.extractall(sd, filter="data")')
s=replace_once(s,'ids, info = changed_window(ids, R, pos)', '''if os.environ["R56_ARM"] == "t":
    ids, info = changed_window(ids, R, pos)
else:
    info = dict(width=len(ids), changed=0, membership_sha256=hashlib.sha256(np.sort(ids).astype("<i8").tobytes()).hexdigest())
if len(ids)!=80000 or len(np.unique(ids))!=80000: raise RuntimeError("Invalid comparison width")''')
if prep:
    s=replace_once(s,"RK = ekeys(np.arange(n))",'''rows, costs = starting_pool(Lc, NN, fx, ln, S * 99991 + CY * 31)
if len(rows)!=100 or len({ekeys(t).tobytes() for t in rows})!=100 or any(fl(t)!=FL0+d for t,d in zip(rows,costs)):
    raise RuntimeError("Starting pool check failed")
print(json.dumps(dict(arm=os.environ["R56_ARM"],width=n,frozen=int(len(F)),base=int(R0),changed=int(info["changed"]),pool=len(rows))))
raise SystemExit(0)''')
s=replace_once(s, '''log(f"done gain={rep['gain']}")''', '''log(f"done gain={rep['gain']}")
Path("summary.json").write_text(json.dumps(dict(arm=os.environ["R56_ARM"],width=n,frozen=int(len(F)),
    baseline=int(R0),changed=int(info["changed"]),membership=info["membership_sha256"],
    gain=int(rep["gain"]),work_units=len(rep["isl"]),seconds=round(time.time()-t0),
    numpy=np.__version__),separators=(",",":"))+"\\n")''')
exec(compile(s,str(p),"exec"),{"__file__":str(p),"__name__":"__main__"})
