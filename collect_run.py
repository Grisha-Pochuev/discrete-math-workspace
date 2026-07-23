#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import zipfile

import batch


ROOT = Path(__file__).resolve().parent
PREVIOUS_VERIFY = ROOT / "runs" / "2026-07-22-a" / "verify.py"
INCOMPLETE_STATUSES = {"capacity", "timeout", "stopped", "deadline_kill", "memory"}
ALLOWED_STATUSES = {"complete"} | INCOMPLETE_STATUSES


def load_exact_verifier():
    spec = importlib.util.spec_from_file_location("previous_exact_verify", PREVIOUS_VERIFY)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {PREVIOUS_VERIFY}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EXACT = load_exact_verifier()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def task_from_dict(item: dict[str, object]) -> batch.Task:
    return batch.Task(
        str(item["stage"]),
        int(item["orbit"]),
        int(item["limit"]),
        int(item["shard"]),
        int(item["shards"]),
        int(item.get("split", 15)),
        int(item.get("max_seen", 0)),
    )


def load_source_tasks(path: Path, expected_lane: str) -> tuple[dict[str, object], list[batch.Task]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if str(document.get("stage")) != expected_lane:
        raise RuntimeError(
            f"source task lane mismatch: expected {expected_lane}, got {document.get('stage')}"
        )
    tasks = [task_from_dict(item) for item in document["tasks"]]
    names = [task.name for task in tasks]
    if len(names) != len(set(names)):
        raise RuntimeError("duplicate source task names")
    return document, tasks


def read_records(zf: zipfile.ZipFile) -> list[dict[str, object]]:
    if "records.jsonl" not in zf.namelist():
        raise RuntimeError("records.jsonl missing")
    return [
        json.loads(line)
        for line in zf.read("records.jsonl").decode("utf-8").splitlines()
        if line.strip()
    ]


def read_resources(zf: zipfile.ZipFile) -> list[dict[str, int | float]]:
    lines = zf.read("resources.tsv").decode("utf-8").splitlines()
    if not lines:
        raise RuntimeError("empty resources.tsv")
    header = lines[0].split("\t")
    rows: list[dict[str, int | float]] = []
    for line in lines[1:]:
        if not line.strip():
            continue
        values = dict(zip(header, line.split("\t")))
        rows.append(
            {
                "elapsed_s": float(values["elapsed_s"]),
                "rss_bytes": int(values["rss_bytes"]),
                "mem_available_bytes": int(values["mem_available_bytes"]),
                "swap_used_bytes": int(values["swap_used_bytes"]),
                "active": int(values["active"]),
                "pending": int(values["pending"]),
            }
        )
    return rows


def parse_solution(text: str) -> int:
    size_text, mask_text = text.split()
    mask = int(mask_text, 16)
    if mask.bit_count() != int(size_text):
        raise RuntimeError(f"bad support size: {text}")
    if not EXACT.is_closed(mask):
        raise RuntimeError(f"support is not closed: {text}")
    return mask


def validate_record_against_task(record: dict[str, object], task: batch.Task) -> None:
    expected = asdict(task)
    for key in ("stage", "orbit", "limit", "shard", "shards", "split", "max_seen"):
        actual = record.get(key)
        wanted = expected[key]
        if str(actual) != str(wanted):
            raise RuntimeError(
                f"{task.name}: record field {key} mismatch: {actual!r} != {wanted!r}"
            )


def analyse(
    raw_dir: Path,
    source_tasks: list[batch.Task],
    manifest_stage: str,
    job_count: int,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    archives = sorted(raw_dir.glob("data-*.zip"), key=lambda path: int(path.stem[5:]))
    if len(archives) != job_count:
        raise RuntimeError(f"expected {job_count} artifacts, found {len(archives)}")

    source_by_name = {task.name: task for task in source_tasks}
    jobs: set[int] = set()
    records: list[dict[str, object]] = []
    record_names: set[str] = set()
    unstarted_names: set[str] = set()
    supports: list[int] = []
    max_rss = 0
    min_available: int | None = None
    max_swap = 0
    resource_elapsed = 0.0
    cpu_models: Counter[str] = Counter()

    for archive in archives:
        with zipfile.ZipFile(archive) as zf:
            names = set(zf.namelist())
            mandatory = {"manifest.json", "records.jsonl", "resources.tsv", "system.txt"}
            missing = mandatory - names
            if missing:
                raise RuntimeError(f"{archive.name}: missing {sorted(missing)}")
            bad = zf.testzip()
            if bad is not None:
                raise RuntimeError(f"{archive.name}: corrupt member {bad}")

            manifest = json.loads(zf.read("manifest.json"))
            job_id = int(manifest["job_id"])
            if job_id in jobs:
                raise RuntimeError(f"duplicate job {job_id}")
            jobs.add(job_id)
            if not 0 <= job_id < job_count:
                raise RuntimeError(f"invalid job id {job_id}")
            if int(manifest["job_count"]) != job_count:
                raise RuntimeError(f"{archive.name}: job_count mismatch")
            if str(manifest["stage"]) != manifest_stage:
                raise RuntimeError(
                    f"{archive.name}: manifest stage {manifest['stage']} != {manifest_stage}"
                )

            artifact_records = read_records(zf)
            if len(artifact_records) != int(manifest["recorded"]):
                raise RuntimeError(f"{archive.name}: record count mismatch")
            artifact_unstarted = [str(name) for name in manifest.get("unstarted", [])]
            if len(artifact_unstarted) != len(set(artifact_unstarted)):
                raise RuntimeError(f"{archive.name}: duplicate unstarted names")

            expected_job_names = {task.name for task in source_tasks[job_id::job_count]}
            actual_job_names = {str(record["name"]) for record in artifact_records} | set(
                artifact_unstarted
            )
            if actual_job_names != expected_job_names:
                missing_job = sorted(expected_job_names - actual_job_names)
                extra_job = sorted(actual_job_names - expected_job_names)
                raise RuntimeError(
                    f"{archive.name}: source coverage mismatch; missing={missing_job[:5]}, "
                    f"extra={extra_job[:5]}"
                )
            if int(manifest["assigned"]) != len(expected_job_names):
                raise RuntimeError(f"{archive.name}: assigned count mismatch")

            for name in artifact_unstarted:
                if name in record_names or name in unstarted_names:
                    raise RuntimeError(f"duplicate task outcome {name}")
                unstarted_names.add(name)

            for record in artifact_records:
                name = str(record["name"])
                if name in record_names or name in unstarted_names:
                    raise RuntimeError(f"duplicate task outcome {name}")
                task = source_by_name.get(name)
                if task is None:
                    raise RuntimeError(f"unexpected task {name}")
                validate_record_against_task(record, task)
                status = str(record["status"])
                if status not in ALLOWED_STATUSES:
                    raise RuntimeError(f"{name}: unexpected status {status}")
                record_names.add(name)
                records.append(record)
                for solution in record.get("solutions", []):
                    supports.append(parse_solution(str(solution)))

            for row in read_resources(zf):
                max_rss = max(max_rss, int(row["rss_bytes"]))
                available = int(row["mem_available_bytes"])
                min_available = available if min_available is None else min(
                    min_available, available
                )
                max_swap = max(max_swap, int(row["swap_used_bytes"]))
                resource_elapsed = max(resource_elapsed, float(row["elapsed_s"]))

            system = zf.read("system.txt").decode("utf-8", errors="replace")
            match = re.search(r"Model name:\s*(.+)", system)
            if not match:
                match = re.search(r"model name\s*:\s*(.+)", system, re.I)
            if match:
                cpu_models[match.group(1).strip()] += 1

    if jobs != set(range(job_count)):
        raise RuntimeError(f"job ids mismatch: {sorted(jobs)}")
    all_outcomes = record_names | unstarted_names
    expected_all = set(source_by_name)
    if all_outcomes != expected_all:
        raise RuntimeError("global source task coverage mismatch")

    status_counts = Counter(str(record["status"]) for record in records)
    limits = sorted({int(record["limit"]) for record in records})
    layer_status = {
        str(limit): dict(
            Counter(
                str(record["status"])
                for record in records
                if int(record["limit"]) == limit
            )
        )
        for limit in limits
    }
    unique_supports = set(supports)
    outcomes = {mask: EXACT.analyse_support(mask) for mask in unique_supports}
    unresolved_supports = sorted(
        mask for mask, outcome in outcomes.items() if outcome == "unresolved"
    )
    if unresolved_supports:
        raise RuntimeError(
            f"{len(unresolved_supports)} supports lack an exact obstruction"
        )

    incomplete_records = [
        record
        for record in records
        if str(record["status"]) in INCOMPLETE_STATUSES
    ]
    summary: dict[str, object] = {
        "run_id": None,
        "source_commit": None,
        "source_task_parent_run": None,
        "source_lane": None,
        "manifest_stage": manifest_stage,
        "artifacts": len(archives),
        "jobs": sorted(jobs),
        "source_tasks": len(source_tasks),
        "tasks": {
            "recorded": len(records),
            "complete": status_counts.get("complete", 0),
            "incomplete": len(incomplete_records),
            "unstarted": len(unstarted_names),
            "status_counts": dict(status_counts),
        },
        "layers": layer_status,
        "search": {
            "nodes": sum(int(record.get("nodes", 0)) for record in records),
            "states": sum(int(record.get("seen", 0)) for record in records),
            "engine_seconds": sum(
                float(record.get("seconds", 0.0)) for record in records
            ),
        },
        "resources": {
            "max_combined_rss_bytes": max_rss,
            "min_mem_available_bytes": min_available or 0,
            "max_swap_used_bytes": max_swap,
            "max_observed_elapsed_seconds": resource_elapsed,
            "cpu_models": dict(cpu_models),
        },
        "supports": {
            "occurrences": len(supports),
            "unique": len(unique_supports),
            "unique_by_size": dict(Counter(mask.bit_count() for mask in unique_supports)),
            "exact_obstructions": dict(Counter(outcomes.values())),
        },
        "incomplete_task_names": sorted(str(record["name"]) for record in incomplete_records),
        "unstarted_task_names": sorted(unstarted_names),
    }
    return summary, records


def next_frontier(
    source_tasks: list[batch.Task],
    records: list[dict[str, object]],
    reserve_limit: int,
    reserve_shards: int,
    reserve_split: int,
    refinement_factor: int,
) -> tuple[list[batch.Task], dict[str, int]]:
    record_by_name = {str(record["name"]): record for record in records}
    if len(record_by_name) != len(records):
        raise RuntimeError("duplicate record names")

    refined: list[batch.Task] = []
    carried: list[batch.Task] = []
    for task in source_tasks:
        record = record_by_name.get(task.name)
        if record is None:
            carried.append(task)
            continue
        status = str(record["status"])
        if status == "complete":
            continue
        if status not in INCOMPLETE_STATUSES:
            raise RuntimeError(f"cannot continue status {status} for {task.name}")
        effective_max_seen = int(record.get("effective_max_seen", 0)) or task.max_seen
        for child in range(refinement_factor):
            refined.append(
                batch.Task(
                    "h",
                    task.orbit,
                    task.limit,
                    task.shard + task.shards * child,
                    task.shards * refinement_factor,
                    task.split,
                    effective_max_seen,
                )
            )

    reserve = [
        batch.Task("i", orbit, reserve_limit, shard, reserve_shards, reserve_split, 0)
        for shard in range(reserve_shards)
        for orbit in range(8)
    ]
    tasks = refined + carried + reserve
    names = [task.name for task in tasks]
    if len(names) != len(set(names)):
        raise RuntimeError("duplicate next-frontier task")
    counts = [sum(1 for index in range(len(tasks)) if index % 20 == job) for job in range(20)]
    if max(counts) - min(counts) > 1:
        raise RuntimeError("unbalanced next frontier")
    return tasks, {
        "refined": len(refined),
        "carried": len(carried),
        "reserve": len(reserve),
    }


def write_readme(output: Path, summary: dict[str, object]) -> None:
    tasks = summary["tasks"]
    supports = summary["supports"]
    resources = summary["resources"]
    nxt = summary["next_frontier"]
    text = f"""# Batch run {summary['run_id']}

Source run: https://github.com/Grisha-Pochuev/discrete-math-workspace/actions/runs/{summary['run_id']}

The archive was rebuilt from all twenty original GitHub artifact ZIP files. Every recorded or unstarted task was checked against the exact source task list used by the run.

## Search outcome

- source tasks: {summary['source_tasks']}
- recorded tasks: {tasks['recorded']}
- complete tasks: {tasks['complete']}
- incomplete bounded tasks: {tasks['incomplete']}
- unstarted tasks: {tasks['unstarted']}
- nodes: {summary['search']['nodes']:,}
- states: {summary['search']['states']:,}
- engine seconds: {summary['search']['engine_seconds']:.3f}

## Exact support checks

- support occurrences: {supports['occurrences']}
- unique closed supports: {supports['unique']}
- exact obstruction counts: `{json.dumps(supports['exact_obstructions'], sort_keys=True)}`
- unresolved exact checks: 0

## Resources

- peak combined RSS on one runner: {resources['max_combined_rss_bytes']:,} bytes
- minimum observed MemAvailable: {resources['min_mem_available_bytes']:,} bytes
- maximum observed swap use: {resources['max_swap_used_bytes']:,} bytes

## Successor frontier

`next_tasks.json` contains {nxt['tasks']:,} exact tasks:

1. {nxt['refined']:,} refined children of recorded incomplete tasks;
2. {nxt['carried']:,} exact source tasks that were never started;
3. {nxt['reserve']:,} reserve tasks from support-size layer {nxt['reserve_limit']}.

Completed tasks are not repeated. Refined child indices satisfy `child mod parent_shards = parent_shard`, so each refinement is an exact partition of only its unresolved parent.
"""
    (output / "README.md").write_text(text, encoding="utf-8")


def write_verifier(output: Path) -> None:
    text = r'''#!/usr/bin/env python3
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
'''
    (output / "verify.py").write_text(text, encoding="utf-8")


def save_run(args: argparse.Namespace) -> dict[str, object]:
    raw_dir = Path(args.raw_dir)
    output = Path(args.output)
    source_path = Path(args.source_tasks)
    source_document, source_tasks = load_source_tasks(source_path, args.source_lane)

    output.mkdir(parents=True, exist_ok=False)
    saved_raw = output / "raw"
    saved_raw.mkdir()
    archives = sorted(raw_dir.glob("data-*.zip"), key=lambda path: int(path.stem[5:]))
    for archive in archives:
        shutil.copy2(archive, saved_raw / archive.name)
    shutil.copy2(source_path, output / "source_tasks.json")

    summary, records = analyse(saved_raw, source_tasks, args.manifest_stage, args.job_count)
    summary["run_id"] = args.run_id
    summary["source_commit"] = args.source_sha
    summary["source_task_parent_run"] = source_document.get("parent_run")
    summary["source_lane"] = args.source_lane

    next_tasks, counts = next_frontier(
        source_tasks,
        records,
        args.reserve_limit,
        args.reserve_shards,
        args.reserve_split,
        args.refinement_factor,
    )
    summary["next_frontier"] = {
        "stage": args.source_lane,
        "tasks": len(next_tasks),
        "by_limit": dict(Counter(task.limit for task in next_tasks)),
        "refined": counts["refined"],
        "carried": counts["carried"],
        "reserve": counts["reserve"],
        "reserve_limit": args.reserve_limit,
        "reserve_shards": args.reserve_shards,
        "reserve_split": args.reserve_split,
        "refinement_factor": args.refinement_factor,
    }

    checksums = [
        f"{sha256(archive)}  raw/{archive.name}\n"
        for archive in sorted(saved_raw.glob("data-*.zip"), key=lambda path: int(path.stem[5:]))
    ]
    (output / "checksums.sha256").write_text("".join(checksums), encoding="utf-8")
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with (output / "records.jsonl").open("w", encoding="utf-8") as target:
        for record in records:
            target.write(json.dumps(record, sort_keys=True) + "\n")
    (output / "next_tasks.json").write_text(
        json.dumps(
            {
                "parent_run": args.run_id,
                "stage": args.source_lane,
                "tasks": [asdict(task) for task in next_tasks],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    write_readme(output, summary)
    write_verifier(output)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--source-tasks", required=True)
    parser.add_argument("--source-lane", default="frontier3")
    parser.add_argument("--manifest-stage", default="frontier2")
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--job-count", type=int, default=20)
    parser.add_argument("--refinement-factor", type=int, default=16)
    parser.add_argument("--reserve-limit", type=int, required=True)
    parser.add_argument("--reserve-shards", type=int, required=True)
    parser.add_argument("--reserve-split", type=int, required=True)
    args = parser.parse_args()
    if args.refinement_factor < 2:
        parser.error("refinement-factor must be at least 2")
    summary = save_run(args)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
