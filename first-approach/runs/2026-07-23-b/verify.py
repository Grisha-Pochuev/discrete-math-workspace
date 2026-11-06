#!/usr/bin/env python3
from pathlib import Path
import hashlib
import json
import zipfile

root = Path(__file__).resolve().parent
summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
lines = (root / "checksums.sha256").read_text(encoding="utf-8").splitlines()
assert len(lines) == summary["artifacts"] == 20
for line in lines:
    expected, relative = line.split()
    digest = hashlib.sha256((root / relative).read_bytes()).hexdigest()
    assert digest == expected
    with zipfile.ZipFile(root / relative) as zf:
        assert {"manifest.json", "records.jsonl", "resources.tsv", "system.txt"} <= set(zf.namelist())
assert summary["jobs"] == list(range(20))
assert summary["supports"]["exact_obstructions"].get("unresolved", 0) == 0
assert summary["resources"]["max_swap_used_bytes"] == 0
print("PASS: 20 checksums, complete job set, exact support exclusions, zero swap")
