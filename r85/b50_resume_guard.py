





import datetime
import hashlib
import json
import os
import re
import sys
from pathlib import Path

PLAN_SHA256 = "f57fa7fa7f82e3eca2024380aec060b0836c8edf53b54cf67e25178b006473d9"
PLAN_FILE = "resume_run_plan.json"
MANIFEST_FILE = "b50_parent_audit.json"
REQUIRED = ["s.json", "st.json", "o.log"] + [f"{kind}{k}.bin" for kind in "cu" for k in range(4)]
POLICY = {"id": "p1", "src3_cloning": False,
          "force_stage2": False, "cross_island_reuse": False,
          "ordinary_migration": True, "reference_injection_islands": [1],
          "late_reference_injection": True, "natural_stage_transitions": True,
          "done_policy": "d1"}


def require(ok, reason):
    if not ok:
        raise RuntimeError("r0: " + reason)


def valid_hash(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON key " + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=unique,
                      parse_constant=lambda value: require(False, "nonfinite JSON value"))


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


def instant(value):
    require(isinstance(value, str) and value.endswith("Z"), "UTC expiry/activation required")
    return datetime.datetime.fromisoformat(value[:-1] + "+00:00")


def header_sha256(header):
    return hashlib.sha256(b"h1\0" + json.dumps(header, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def validate_header(header, population=100):
    require(isinstance(header, list) and len(header) == 10 and all(isinstance(v, str) for v in header), "header shape")
    values = [int(v) for v in header[:9]]
    require(values[0] >= 0 and values[1] in (1, 2) and values[2] in (1, 2)
            and values[8] == population and header[-1] in ("deadline", "done"), "header values")
    return header


def read_header(path):
    with np.load(io.BytesIO(lzma.decompress(Path(path).read_bytes())), allow_pickle=False) as data:
        header = data["h"]
        require(header.ndim == 1 and header.dtype.kind == "U", "header representation")
        return validate_header([str(v) for v in header])


def validate_plan(plan, now):
    require(plan.get("schema_version") == 3, "run-plan schema")
    require(plan.get("status") == "r1", "run plan not reviewed")
    require(isinstance(plan.get("plan_id"), str) and bool(plan["plan_id"]), "plan ID")
    require(instant(plan["not_before_utc"]) <= now < instant(plan["expires_at_utc"]), "plan inactive or expired")
    require(plan.get("stage_policy") == POLICY, "unreviewed stage policy")
    require(plan.get("automatic_repeats") == 0 and plan.get("production_waves") == 1, "wave/repeat policy")
    parent, target = plan["parent"], plan["target"]
    require(type(parent.get("run_id")) is int and parent["run_id"] > 0, "parent run ID")
    require(type(parent.get("cycle")) is int and type(parent.get("report_version")) is int, "parent cycle/version")
    require(type(target.get("cycle")) is int and target["cycle"] == parent["cycle"] + 1, "target cycle must follow parent")
    require(type(parent.get("base_marker")) is int, "public-safe base marker")
    require(re.fullmatch(r"[0-9a-f]{40}", parent.get("public_commit", "")) is not None, "parent commit")
    for field in ("driver_sha256", "guard_sha256", "geometry_sha256"):
        require(valid_hash(parent.get(field)), "parent " + field)
    seeds = target.get("seeds", [])
    require(len(seeds) == 20 and all(type(s) is int for s in seeds), "exact 20 seed IDs required")
    require(seeds == list(range(seeds[0], seeds[0] + 20)) and seeds[0] % 20 == 0, "seed/window mapping")
    require(target.get("population") == 100 and target.get("offspring") == 30
            and target.get("islands") == 4 and target.get("dimension") == 80000, "supported search dimensions")
    require(type(target.get("budget_seconds")) is int and 0 < target["budget_seconds"] <= 20700, "reviewed budget")
    require(target.get("q") == f"100,30,{target['cycle']}", "target Q/cycle mismatch")
    require(valid_hash(plan.get("manifest_sha256")), "reviewed manifest hash missing")
    review = plan.get("review", {})
    require(review.get("reviewer") == "r0" and valid_hash(review.get("approval_evidence")), "review digest required")
    files = plan.get("runtime_files", {})
    require(set(files) == {"driver", "helper", "geometry", "workflow"}, "runtime file contract")
    expected_paths = {"driver": "e33_g24_resume.py", "helper": "ab_cap_patch.py",
                      "geometry": "g24.bin", "workflow": ".github/workflows/r86.yml"}
    for key, path in expected_paths.items():
        require(files[key].get("path") == path and valid_hash(files[key].get("sha256")), "runtime " + key)
    require(files["geometry"]["sha256"] == parent["geometry_sha256"], "geometry change is not a resume")


def validate_environment(env, target):
    exact = {"S2": "0", "S2R": "", "SRC3": "0", "AG": "0", "SGF": "g24",
             "HF": "", "NW": "", "DRP": "", "RO": "", "BIK": "1", "W": "4",
             "FX": "200000", "LP": "999999999", "DS": "50", "QW": "50", "RW": "0.25",
             "AV": "1", "CK": "1800", "MS": "360", "RS": "2400", "LOCAL": "",
             "CXX": "g++ -O3 -march=native", "PERT": "14", "MT": "3000", "TLX": "0"}
    for key, value in exact.items():
        require(key not in env or env[key] == value, "unexpected " + key)
    require(env.get("Q") == target["q"], "Q differs from exact reviewed target")
    require(set(env.get("SMS", ",".join(map(str, range(20)))).split(",")) == set(map(str, range(20))), "SMS changes geometry")
    for key in env:
        if key.startswith("GA_"):
            require(key == "GA_AB_CAP_POLICY" and env[key] == "single", "unexpected solver override " + key)


def validate_manifest(manifest, plan):
    p, t = plan["parent"], plan["target"]
    require(manifest.get("schema_version") == 3, "manifest schema")
    require(manifest.get("status") == "m1", "parent review pending")
    expected = {"parent_run": p["run_id"], "parent_cycle": p["cycle"], "parent_report_version": p["report_version"],
                "parent_public_commit": p["public_commit"], "parent_driver_sha256": p["driver_sha256"],
                "parent_guard_sha256": p["guard_sha256"], "geometry_sha256": p["geometry_sha256"],
                "base_marker": p["base_marker"], "population": t["population"], "islands": t["islands"],
                "dimension": t["dimension"], "stage_policy": POLICY}
    for key, value in expected.items():
        require(manifest.get(key) == value, "manifest/plan mismatch " + key)
    require(manifest.get("candidate_evidence_resolved") is True, "unresolved candidate evidence")
    require(set(manifest.get("seeds", {})) == set(map(str, t["seeds"])), "complete 20-seed manifest required")
                                                                 
    for s, item in manifest["seeds"].items():
        hashes = item.get("sha256", {})
        require(set(hashes) == set(REQUIRED + ["m.bin"]), "parent file set " + s)
        for name, value in hashes.items():
            require((name == "m.bin" and value is None) or valid_hash(value), "parent digest " + s + "/" + name)
        headers = item.get("header_sha256", {})
        require(set(headers) == set(map(str, range(4))) and all(valid_hash(h) for h in headers.values()), "four parent header digests " + s)
        identities = item.get("population_identity_sha256", {})
        require(set(identities) == set(map(str, range(4))) and all(valid_hash(h) for h in identities.values()), "audited population identities " + s)


def validate_parent_files(manifest, plan, seed, parent):
    validate_manifest(manifest, plan)
    p, t = plan["parent"], plan["target"]
    entry = manifest["seeds"][str(seed)]
    for name, expected_hash in entry["sha256"].items():
        path = parent / name
        if expected_hash is None:
            require(not path.exists(), "unexpected migration bank")
        else:
            require(path.is_file() and sha256(path) == expected_hash, "missing/changed parent " + name)
    summary = read_json(parent / "s.json")
    for key, value in {"s": seed, "ri": seed % 20, "cy": p["cycle"], "v": p["report_version"], "sm": 1, "hd": 0, "abp": "single"}.items():
        require(summary.get(key) == value, "parent summary " + key)
    state = read_json(parent / "st.json")
    require(state.get("sm") == 1 and set(state.get("isl", {})) == set(map(str, range(4))), "parent island state")
    for island in state["isl"].values():
        require(type(island.get("tr")) is int and island["tr"] >= 0, "restart counter")
    rows = summary.get("isl", [])
    require(len(rows) == 4 and {r.get("k") for r in rows} == set(range(4)), "summary island coverage")
    by_island = {str(r["k"]): r for r in rows}
    for key, row in by_island.items():
        hdr = read_header(parent / f"c{key}.bin")
        require(header_sha256(hdr) == entry["header_sha256"][key], "parent header digest")
        require((row.get("g"), row.get("st"), row.get("tag"), row.get("np")) == (int(hdr[0]), int(hdr[1]), hdr[9], 100), "summary/header agreement")
        require(type(row.get("b")) in (int, float) and type(row.get("a")) in (int, float), "summary costs missing")
    return dict(entry, _summary=by_island, _contract={"population": t["population"], "dimension": t["dimension"], "islands": t["islands"]})


def preflight(driver_file, argv=None, env=None, parent=None):
    require(valid_hash(PLAN_SHA256), "no exact reviewed plan bound")
    argv = sys.argv if argv is None else argv
    env = os.environ if env is None else env
    parent = Path("p") if parent is None else Path(parent)
    root = Path(driver_file).resolve().parent
    require(sha256(root / PLAN_FILE) == PLAN_SHA256, "run-plan hash mismatch")
    plan = read_json(root / PLAN_FILE)
    validate_plan(plan, utcnow())
    validate_environment(env, plan["target"])
    require(len(argv) == 3, "expected seed and budget arguments")
    seed, budget = map(int, argv[1:])
    require(seed in plan["target"]["seeds"] and budget == plan["target"]["budget_seconds"], "seed/budget not reviewed")
    for key in ("driver", "helper", "geometry"):
        item = plan["runtime_files"][key]
        path = Path(driver_file).resolve() if key == "driver" else root / item["path"]
        require(path.name == item["path"] and sha256(path) == item["sha256"], "runtime file hash " + key)
                                                                                
                                                                            
    workflow = root.parent / plan["runtime_files"]["workflow"]["path"]
    if workflow.exists():
        require(sha256(workflow) == plan["runtime_files"]["workflow"]["sha256"], "workflow hash mismatch")
    require(not Path("wd/x").exists(), "cached executable")
    require(not (root / "a.bin").exists() and not (root / f"a24_{seed % 20}.bin").exists(), "unreviewed alternative bank")
    require(sha256(root / MANIFEST_FILE) == plan["manifest_sha256"], "parent manifest hash mismatch")
    return validate_parent_files(read_json(root / MANIFEST_FILE), plan, seed, parent)


def population_identity_sha256(adjacencies):

    identity = hashlib.sha256(b"population-adjacency-v1\0")
    for adj in adjacencies:
        require(adj.dtype == np.dtype("<u4") and adj.ndim == 2 and adj.shape[1] == 2, "canonical adjacency representation")
        identity.update(hashlib.sha256(adj.tobytes(order="C")).digest())
    return identity.hexdigest()


def validate_decoded_parent(entry, parent, decode, npop, ncity, cost, adjacency):
    contract = entry["_contract"]
    require(npop == contract["population"] and ncity == contract["dimension"], "problem dimensions")
    baseline = cost(np.arange(ncity))
    require(baseline is not None, "base sequence fixed edges")
    for k in range(contract["islands"]):
        raw = (parent / f"c{k}.bin").read_bytes()
        require(hashlib.sha256(raw).hexdigest() == entry["sha256"][f"c{k}.bin"], "checkpoint changed after preflight")
        hdr, pop = decode(raw)
        validate_header(hdr, npop)
        require(header_sha256(hdr) == entry["header_sha256"][str(k)] and len(pop) == npop, "decoded audited header/population mismatch")
        values = []
        def checked_adjacencies():
            for seq in pop:
                require(len(seq) == ncity, "sequence size")
                adj = adjacency(seq)
                value = cost(seq)
                require(value is not None, "required fixed edges missing")
                values.append(value)
                yield adj
        identity = population_identity_sha256(checked_adjacencies())
        require(identity == entry["population_identity_sha256"][str(k)], "decoded population identity differs from audit")
        row = entry["_summary"][str(k)]
        require(min(values) - baseline == row["b"], "decoded minimum differs from summary")
        require(abs(float(np.mean(values)) - baseline - row["a"]) <= 1e-6, "decoded mean differs from summary")


                                                               
import io
import lzma
import numpy as np


def strict_decode(raw, nn, n, k, decoder=None):
    with np.load(io.BytesIO(lzma.decompress(raw)), allow_pickle=False) as z:
        if set(z.files) != {"a", "e", "h"}:
            raise ValueError("checkpoint array set")
        a, e, header = z["a"], z["e"], z["h"]
    if a.dtype != np.uint8 or a.ndim != 2 or a.shape[1] != n:
        raise ValueError("checkpoint neighbor rank dimensions/dtype")
    if np.any((a >= k) & (a != 255)):
        raise ValueError("invalid nearest-neighbor rank")
    if e.dtype != np.int64 or e.ndim != 2 or e.shape[1] != 3:
        raise ValueError("checkpoint exception dimensions/dtype")
    if header.ndim != 1 or header.dtype.kind != "U":
        raise ValueError("checkpoint header dimensions/dtype")
    if e.size and (np.any(e < 0) or np.any(e[:, 0] >= len(a)) or np.any(e[:, 1:] >= n)):
        raise ValueError("checkpoint exception index out of range")
    positions = e[:, 0] * n + e[:, 1]
    missing = np.flatnonzero(a.reshape(-1) == 255)
    if not np.array_equal(np.sort(positions), missing):
        raise ValueError("checkpoint missing/duplicate/unexpected exception")
    if nn.shape != (n, k):
        raise ValueError("checkpoint neighbor-table dimensions")
    original = decoder(raw) if decoder is not None else None
    if original is not None and (original[0] != [str(v) for v in header] or len(original[1]) != len(a)):
        raise ValueError("decoded header/population does not match encoding")
    seqs = []
    for j in range(len(a)):
        successors = nn[np.arange(n), np.minimum(a[j], k - 1)].astype(np.int64)
        extra = e[e[:, 0] == j]
        successors[extra[:, 1]] = extra[:, 2]
        if np.any(successors < 0) or np.any(successors >= n) or not np.all(np.bincount(successors, minlength=n) == 1):
            raise ValueError("checkpoint successor indegree is not one")
        if original is None:
            sl = successors.tolist()
            route = [0] * n
            vertex = 0
            for i in range(n):
                route[i] = vertex
                vertex = sl[vertex]
            seq = np.asarray(route, dtype=np.int64)
        else:
            seq = np.asarray(original[1][j], dtype=np.int64)
        if (len(seq) != n or np.any(seq < 0) or np.any(seq >= n)
                or not np.all(np.bincount(seq, minlength=n) == 1)
                or not np.array_equal(successors[seq], np.roll(seq, -1))):
            raise ValueError("checkpoint is not one closed Hamiltonian cycle")
        seqs.append(seq)
    return [str(v) for v in header], seqs


def validate_migration_bank(path, decoder, nn, n, k, cost, adjacency):

    if not path.exists():
        return
    header, seqs = strict_decode(path.read_bytes(), nn, n, k, decoder=decoder)
    if header:
        raise ValueError("migration bank unexpectedly contains checkpoint header")
    for seq in seqs:
        adjacency(seq)
        if cost(seq) is None:
            raise ValueError("migration bank missing required fixed edges")
