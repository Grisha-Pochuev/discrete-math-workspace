#!/usr/bin/env python3
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parent
repo = root.parents[1]
summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
source_document = json.loads((root / "source_tasks.json").read_text(encoding="utf-8"))
source_tasks = source_document["tasks"]
source_names = [
    f"{item['stage']}-o{int(item['orbit'])}-l{int(item['limit'])}-s{int(item['shard']):05d}-of-{int(item['shards'])}"
    for item in source_tasks
]
assert len(source_names) == len(set(source_names)) == summary["source_tasks"]

spec = importlib.util.spec_from_file_location(
    "exact_verify", repo / "runs" / "2026-07-22-a" / "verify.py"
)
assert spec is not None and spec.loader is not None
exact = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exact)

checksum_lines = (root / "checksums.sha256").read_text(encoding="utf-8").splitlines()
checksums = {name: digest for digest, name in (line.split() for line in checksum_lines)}
archives = sorted((root / "raw").glob("data-*.zip"), key=lambda path: int(path.stem[5:]))
assert len(archives) == summary["artifacts"] == len(checksums) == 20

all_records = []
all_unstarted = set()
jobs = set()
supports = []
max_rss = 0
min_available = None
max_swap = 0
for archive in archives:
    relative = archive.relative_to(root).as_posix()
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == checksums[relative]
    with zipfile.ZipFile(archive) as zf:
        assert zf.testzip() is None
        assert {"manifest.json", "records.jsonl", "resources.tsv", "system.txt"} <= set(zf.namelist())
        manifest = json.loads(zf.read("manifest.json"))
        job = int(manifest["job_id"])
        jobs.add(job)
        records = [json.loads(line) for line in zf.read("records.jsonl").decode().splitlines() if line.strip()]
        assert len(records) == int(manifest["recorded"])
        unstarted = set(map(str, manifest.get("unstarted", [])))
        actual = {str(record["name"]) for record in records} | unstarted
        expected = set(source_names[job::20])
        assert actual == expected
        assert not (all_unstarted & unstarted)
        all_unstarted |= unstarted
        all_records.extend(records)
        for record in records:
            for solution in record.get("solutions", []):
                size_text, mask_text = str(solution).split()
                mask = int(mask_text, 16)
                assert mask.bit_count() == int(size_text)
                assert exact.is_closed(mask)
                supports.append(mask)
        lines = zf.read("resources.tsv").decode().splitlines()
        header = lines[0].split("\t")
        for line in lines[1:]:
            if not line.strip():
                continue
            values = dict(zip(header, line.split("\t")))
            max_rss = max(max_rss, int(values["rss_bytes"]))
            available = int(values["mem_available_bytes"])
            min_available = available if min_available is None else min(min_available, available)
            max_swap = max(max_swap, int(values["swap_used_bytes"]))

record_names = [str(record["name"]) for record in all_records]
assert len(record_names) == len(set(record_names))
assert set(record_names) | all_unstarted == set(source_names)
assert jobs == set(range(20)) == set(summary["jobs"])
status_counts = Counter(str(record["status"]) for record in all_records)
assert len(all_records) == summary["tasks"]["recorded"]
assert len(all_unstarted) == summary["tasks"]["unstarted"]
assert dict(status_counts) == summary["tasks"]["status_counts"]
assert sum(int(record.get("nodes", 0)) for record in all_records) == summary["search"]["nodes"]
assert sum(int(record.get("seen", 0)) for record in all_records) == summary["search"]["states"]
assert abs(sum(float(record.get("seconds", 0.0)) for record in all_records) - summary["search"]["engine_seconds"]) < 1e-6
assert max_rss == summary["resources"]["max_combined_rss_bytes"]
assert (min_available or 0) == summary["resources"]["min_mem_available_bytes"]
assert max_swap == summary["resources"]["max_swap_used_bytes"] == 0
outcomes = Counter(exact.analyse_support(mask) for mask in set(supports))
assert outcomes.get("unresolved", 0) == 0
assert dict(outcomes) == summary["supports"]["exact_obstructions"]
print("PASS: exact source coverage, 20 ZIP checksums, exact support exclusions, zero swap")
