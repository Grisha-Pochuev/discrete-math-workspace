"""Fail-closed preparation guard. Does not run, schedule or authorize a solver.

The reviewed parent manifest must be supplied after the real B49 audit. It is
not evidence by itself: the manifest and its exact bytes require review.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

G24_SHA256 = "3961c3959ce870f888540897550659fdf3ed3ed8eb168adf08101683c465b0e2"
E34_SHA256 = "fce5b0b45de29955affd9bf0918619db5c29eec098b8ebdf12fecf18ffb4afe1"
HELPER_SHA256 = "b33e2d7be879ea66b35314737de35598394242a241148036a9b16f498477b5fe"
PARENT_RUN = 42546059056
BASE_COST = -26
REQUIRED = ["s.json", "st.json", "o.log"] + [f"{kind}{k}.bin" for kind in "cu" for k in range(4)]


def require(ok, reason):
    if not ok:
        raise RuntimeError("B50 resume blocked: " + reason)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_environment(env):
    exact = {"S2": "0", "S2R": "", "SRC3": "0", "AG": "0",
             "SGF": "g24", "HF": "", "NW": "", "DRP": "", "RO": "",
             "BIK": "1", "W": "4", "FX": "200000", "LP": "999999999",
             "DS": "50", "QW": "50", "RW": "0.25", "AV": "1",
             "CK": "1800", "MS": "360", "RS": "2400", "LOCAL": "",
             "CXX": "g++ -O3 -march=native"}
    for key, value in exact.items():
        require(key not in env or env[key] == value, f"unexpected {key}")
    require(env.get("Q") == "100,30,51", "Q must be 100,30,51")
    require(set(env.get("SMS", ",".join(map(str, range(20)))).split(",")) == set(map(str, range(20))), "SMS changes geometry selection")
    for key in env:
        if key.startswith("GA_"):
            require(key == "GA_AB_CAP_POLICY" and env[key] == "single", f"unexpected solver override {key}")


def validate_parent_files(manifest, seed, parent):
    require(manifest.get("schema_version") == 1, "manifest schema")
    require(manifest.get("status") == "PARENT_AUDIT_VERIFIED_HARK_REVIEWED", "real parent audit and HARK review are still pending")
    expected = {"parent_run": PARENT_RUN, "geometry_sha256": G24_SHA256,
                "parent_driver_sha256": E34_SHA256, "base_cost": BASE_COST,
                "parent_cycle": 50, "population": 100, "islands": 4}
    for key, value in expected.items():
        require(manifest.get(key) == value, f"manifest {key}")
    require(manifest.get("candidate_evidence_resolved") is True, "unresolved candidate evidence")
    require(manifest.get("done_policy") == "original_e33_fresh_restart", "done restart policy must be explicit")
    require(set(manifest.get("seeds", {})) == set(map(str, range(120, 140))), "manifest must cover all 20 seeds")
    entry = manifest["seeds"][str(seed)]
    hashes = entry.get("sha256", {})
    require(set(hashes) == set(REQUIRED + ["m.bin"]), "parent manifest file set")
    for name in REQUIRED + ["m.bin"]:
        digest = hashes[name]
        path = parent / name
        if name == "m.bin" and digest is None:
            require(not path.exists(), "unexpected migration bank")
        else:
            require(isinstance(digest, str) and len(digest) == 64, f"invalid digest {name}")
            require(path.is_file(), f"missing parent {name}")
            require(sha256(path) == digest, f"parent hash mismatch {name}")
    summary = json.loads((parent / "s.json").read_text())
    for key, value in {"s": seed, "ri": seed % 20, "cy": 50, "v": 34, "sm": 1, "hd": 0}.items():
        require(summary.get(key) == value, f"parent summary {key}")
    state = json.loads((parent / "st.json").read_text())
    require(state.get("sm") == 1, "parent SEAM marker missing")
    require(set(state.get("isl", {})) == set(map(str, range(4))), "parent island state incomplete")
    for island in state["isl"].values():
        require(type(island.get("tr")) is int and island["tr"] >= 0, "invalid restart counter")
    require(set(entry.get("headers", {})) == set(map(str, range(4))), "audited headers missing")
    return entry


def preflight(driver_file, argv=None, env=None, parent=None):
    argv = sys.argv if argv is None else argv
    env = os.environ if env is None else env
    parent = Path("p") if parent is None else Path(parent)
    validate_environment(env)
    require(len(argv) == 3, "expected seed and budget arguments")
    seed, budget = map(int, argv[1:])
    require(120 <= seed < 140 and budget == 19800, "unexpected seed or budget")
    root = Path(driver_file).resolve().parent
    require(sha256(root / "g24.bin") == G24_SHA256, "g24 geometry hash")
    require(sha256(root / "ab_cap_patch.py") == HELPER_SHA256, "AB-cap helper hash")
    require(not Path("wd/x").exists(), "cached executable is not reviewed")
    require(not (root / "a.bin").exists() and not (root / f"a24_{seed % 20}.bin").exists(), "unreviewed alternative bank")
    manifest = json.loads((root / "b50_parent_audit.json").read_text())
    return validate_parent_files(manifest, seed, parent)


def validate_decoded_parent(entry, parent, decode, npop, ncity, cost, adjacency):
    """Validate true decoded bytes against audit before setup can use them."""
    require(npop == 100 and ncity == 80000, "unexpected problem dimensions")
    for k in range(4):
        hdr, pop = decode((parent / f"c{k}.bin").read_bytes())
        require(len(hdr) == 10 and hdr == entry["headers"][str(k)], f"header differs from audited c{k}")
        nums = [int(x) for x in hdr[:9]]
        require(nums[0] >= 0 and nums[1] in (1, 2) and nums[2] in (1, 2), f"invalid stage/header c{k}")
        require(nums[8] == len(pop) == npop, f"partial population c{k}")
        require(hdr[-1] in ("deadline", "periodic", "done", "abcap", "init"), f"unexpected checkpoint tag c{k}")
        for seq in pop:
            require(len(seq) == ncity, f"seq size c{k}")
            adjacency(seq)  # Actual driver's permutation check; no solver.
            require(cost(seq) is not None, f"fixed edges missing c{k}")



# Additional raw codec integrity checks, pending review.
"""Proposed non-optimizing integrity decoder for parent audit/preflight.

No driver defaults, setup policy or encoded file bytes are changed.
"""
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
    """Check only optional parent m.bin, not u*.bin or neighboring q/m.bin."""
    if not path.exists():
        return
    header, seqs = strict_decode(path.read_bytes(), nn, n, k, decoder=decoder)
    if header:
        raise ValueError("migration bank unexpectedly contains checkpoint header")
    for seq in seqs:
        adjacency(seq)
        if cost(seq) is None:
            raise ValueError("migration bank missing required fixed edges")
