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


def read_records(zf: zipfile.ZipFile) -> list[dict[str, object]]:
    names = set(zf.namelist())
    if "records.jsonl" not in names:
        raise RuntimeError("records.jsonl missing")
    return [json.loads(line) for line in zf.read("records.jsonl").decode("utf-8").splitlines()
            if line.strip()]


def read_resources(zf: zipfile.ZipFile) -> list[dict[str, int | float]]:
    lines = zf.read("resources.tsv").decode("utf-8").splitlines()
    if not lines:
        raise RuntimeError("empty resources.tsv")
    header = lines[0].split("\t")
    rows = []
    for line in lines[1:]:
        if not line.strip():
            continue
        values = dict(zip(header, line.split("\t")))
        rows.append({
            "elapsed_s": float(values["elapsed_s"]),
            "rss_bytes": int(values["rss_bytes"]),
            "mem_available_bytes": int(values["mem_available_bytes"]),
            "swap_used_bytes": int(values["swap_used_bytes"]),
            "active": int(values["active"]),
            "pending": int(values["pending"]),
        })
    return rows


def parse_solution(text: str) -> int:
    size_text, mask_text = text.split()
    mask = int(mask_text, 16)
    if mask.bit_count() != int(size_text):
        raise RuntimeError(f"bad support size: {text}")
    if not EXACT.is_closed(mask):
        raise RuntimeError(f"support is not closed: {text}")
    return mask


def analyse(raw_dir: Path, source_stage: str) -> tuple[dict[str, object], list[dict[str, object]]]:
    archives = sorted(raw_dir.glob("data-*.zip"), key=lambda path: int(path.stem[5:]))
    if len(archives) != 20:
        raise RuntimeError(f"expected 20 artifacts, found {len(archives)}")

    jobs: set[int] = set()
    records: list[dict[str, object]] = []
    task_names: set[str] = set()
    unstarted: list[str] = []
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
            manifest = json.loads(zf.read("manifest.json"))
            job_id = int(manifest["job_id"])
            if job_id in jobs:
                raise RuntimeError(f"duplicate job {job_id}")
            jobs.add(job_id)
            if manifest["stage"] != source_stage:
                raise RuntimeError(f"unexpected stage {manifest['stage']}")
            unstarted.extend(str(name) for name in manifest.get("unstarted", []))

            artifact_records = read_records(zf)
            if len(artifact_records) != int(manifest["recorded"]):
                raise RuntimeError(f"{archive.name}: record count mismatch")
            if artifact_records != manifest["records"]:
                raise RuntimeError(f"{archive.name}: manifest/records mismatch")
            for record in artifact_records:
                name = str(record["name"])
                if name in task_names:
                    raise RuntimeError(f"duplicate task {name}")
                task_names.add(name)
                records.append(record)
                for solution in record.get("solutions", []):
                    supports.append(parse_solution(str(solution)))

            for row in read_resources(zf):
                max_rss = max(max_rss, int(row["rss_bytes"]))
                available = int(row["mem_available_bytes"])
                min_available = available if min_available is None else min(min_available, available)
                max_swap = max(max_swap, int(row["swap_used_bytes"]))
                resource_elapsed = max(resource_elapsed, float(row["elapsed_s"]))

            system = zf.read("system.txt").decode("utf-8", errors="replace")
            match = re.search(r"Model name:\s*(.+)", system)
            if not match:
                match = re.search(r"model name\s*:\s*(.+)", system, re.I)
            if match:
                cpu_models[match.group(1).strip()] += 1

    if jobs != set(range(20)):
        raise RuntimeError(f"job ids mismatch: {sorted(jobs)}")

    status_counts = Counter(str(record["status"]) for record in records)
    limits = sorted({int(record["limit"]) for record in records})
    layer_status = {
        str(limit): dict(Counter(str(record["status"]) for record in records
                                 if int(record["limit"]) == limit))
        for limit in limits
    }
    unique_supports = set(supports)
    outcomes = {mask: EXACT.analyse_support(mask) for mask in unique_supports}
    unresolved_supports = sorted(mask for mask, outcome in outcomes.items() if outcome == "unresolved")
    if unresolved_supports:
        raise RuntimeError(f"{len(unresolved_supports)} supports lack an exact obstruction")

    incomplete_statuses = {"capacity", "timeout", "stopped", "deadline_kill", "memory"}
    incomplete_records = [record for record in records if str(record["status"]) in incomplete_statuses]
    unexpected_statuses = sorted(set(status_counts) - ({"complete"} | incomplete_statuses))
    if unexpected_statuses:
        raise RuntimeError(f"unexpected statuses: {unexpected_statuses}")

    summary: dict[str, object] = {
        "run_id": None,
        "source_stage": source_stage,
        "artifacts": len(archives),
        "jobs": sorted(jobs),
        "tasks": {
            "recorded": len(records),
            "complete": status_counts.get("complete", 0),
            "incomplete": len(incomplete_records),
            "unstarted": len(unstarted),
            "status_counts": dict(status_counts),
        },
        "layers": layer_status,
        "search": {
            "nodes": sum(int(record.get("nodes", 0)) for record in records),
            "states": sum(int(record.get("seen", 0)) for record in records),
            "engine_seconds": sum(float(record.get("seconds", 0.0)) for record in records),
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
        "unstarted_task_names": sorted(unstarted),
    }
    return summary, records


def task_from_dict(item: dict[str, object]) -> batch.Task:
    return batch.Task(
        str(item["stage"]), int(item["orbit"]), int(item["limit"]),
        int(item["shard"]), int(item["shards"]), int(item.get("split", 15)),
        int(item.get("max_seen", 0)),
    )


def next_frontier(records: list[dict[str, object]]) -> list[batch.Task]:
    original = batch.frontier2_tasks()
    record_by_name = {str(record["name"]): record for record in records}
    if len(record_by_name) != len(records):
        raise RuntimeError("duplicate record names")

    refined: list[batch.Task] = []
    carried: list[batch.Task] = []
    factor = 16
    for task in original:
        record = record_by_name.get(task.name)
        if record is None:
            carried.append(task)
            continue
        status = str(record["status"])
        if status == "complete":
            continue
        effective_max_seen = int(record.get("effective_max_seen", 0)) or task.max_seen
        for child in range(factor):
            refined.append(batch.Task(
                "f", task.orbit, task.limit,
                task.shard + task.shards * child,
                task.shards * factor, task.split, effective_max_seen,
            ))

    reserve: list[batch.Task] = []
    for shard in range(4096):
        for orbit in range(8):
            reserve.append(batch.Task("g", orbit, 30, shard, 4096, 18, 0))

    tasks = refined + carried + reserve
    names = [task.name for task in tasks]
    if len(names) != len(set(names)):
        raise RuntimeError("duplicate next-frontier task")
    counts = [sum(1 for index in range(len(tasks)) if index % 20 == job) for job in range(20)]
    if max(counts) - min(counts) > 1:
        raise RuntimeError("unbalanced next frontier")
    return tasks


def write_readme(output: Path, summary: dict[str, object], next_tasks: list[batch.Task]) -> None:
    tasks = summary["tasks"]
    supports = summary["supports"]
    resources = summary["resources"]
    text = f"""# Batch run {summary['run_id']}

Source run: https://github.com/Grisha-Pochuev/discrete-math-workspace/actions/runs/{summary['run_id']}

The run completed technically on all 20 matrix jobs. The archive was rebuilt from all twenty original GitHub artifact ZIP files and checked independently.

## Search outcome

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

`next_tasks.json` contains {len(next_tasks):,} exact tasks. Priority order:

1. sixteen-way refinements of every recorded incomplete task;
2. all tasks from the current queue that were never started;
3. support-size layer 30 as a reserve queue so CPU workers do not become idle.

Completed tasks are not repeated. Child shard indices satisfy `child mod parent_shards = parent_shard`, so the refinement is an exact partition of only the unresolved parent.
"""
    (output / "README.md").write_text(text, encoding="utf-8")


def install_frontier3_wiring(output: Path) -> None:
    batch_path = ROOT / "batch.py"
    text = batch_path.read_text(encoding="utf-8")
    if "def frontier3_tasks()" not in text:
        anchor = "\n\ndef all_tasks(stage: str) -> list[Task]:\n"
        insertion = '''\n\ndef frontier3_tasks() -> list[Task]:
    candidates = sorted((Path(__file__).parent / "runs").glob("*/next_tasks.json"))
    if not candidates:
        raise RuntimeError("no saved next_tasks.json")
    document = json.loads(candidates[-1].read_text(encoding="utf-8"))
    return [Task(
        str(item["stage"]), int(item["orbit"]), int(item["limit"]),
        int(item["shard"]), int(item["shards"]), int(item.get("split", 15)),
        int(item.get("max_seen", 0)),
    ) for item in document["tasks"]]
'''
        if anchor not in text:
            raise RuntimeError("batch.py insertion anchor missing")
        text = text.replace(anchor, insertion + anchor, 1)
    text = text.replace(
        '    if stage == "frontier2":\n        return frontier2_tasks()\n',
        '    if stage == "frontier3":\n        return frontier3_tasks()\n    if stage == "frontier2":\n        return frontier2_tasks()\n',
        1,
    )
    text = text.replace(
        'choices=("frontier", "layer26", "layer27", "frontier2"),\n        default="frontier2",',
        'choices=("frontier", "layer26", "layer27", "frontier2", "frontier3"),\n        default="frontier3",',
        1,
    )
    batch_path.write_text(text, encoding="utf-8")

    workflow_path = ROOT / ".github" / "workflows" / "run.yml"
    workflow = workflow_path.read_text(encoding="utf-8")
    workflow = workflow.replace("default: frontier2", "default: frontier3", 1)
    if "          - frontier3\n" not in workflow:
        workflow = workflow.replace("        options:\n          - frontier2\n",
                                    "        options:\n          - frontier3\n          - frontier2\n", 1)
    workflow = workflow.replace("inputs.stage || 'frontier2'", "inputs.stage || 'frontier3'")
    workflow_path.write_text(workflow, encoding="utf-8")


def save_run(run_id: int, source_sha: str, source_stage: str, raw_dir: Path, output: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=False)
    saved_raw = output / "raw"
    saved_raw.mkdir()
    for archive in sorted(raw_dir.glob("data-*.zip"), key=lambda path: int(path.stem[5:])):
        shutil.copy2(archive, saved_raw / archive.name)

    summary, records = analyse(saved_raw, source_stage)
    summary["run_id"] = run_id
    summary["source_commit"] = source_sha
    next_tasks = next_frontier(records)
    summary["next_frontier"] = {
        "stage": "frontier3",
        "tasks": len(next_tasks),
        "by_limit": dict(Counter(task.limit for task in next_tasks)),
        "refined": sum(1 for task in next_tasks if task.stage == "f"),
        "carried": sum(1 for task in next_tasks if task.stage not in {"f", "g"}),
        "reserve": sum(1 for task in next_tasks if task.stage == "g"),
    }

    checksums = []
    for archive in sorted(saved_raw.glob("data-*.zip"), key=lambda path: int(path.stem[5:])):
        checksums.append(f"{sha256(archive)}  raw/{archive.name}\n")
    (output / "checksums.sha256").write_text("".join(checksums), encoding="utf-8")
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n",
                                           encoding="utf-8")
    with (output / "records.jsonl").open("w", encoding="utf-8") as target:
        for record in records:
            target.write(json.dumps(record, sort_keys=True) + "\n")
    (output / "next_tasks.json").write_text(
        json.dumps({"parent_run": run_id, "stage": "frontier3",
                    "tasks": [asdict(task) for task in next_tasks]}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_readme(output, summary, next_tasks)
    (output / "verify.py").write_text(
        '''#!/usr/bin/env python3
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
''', encoding="utf-8")
    install_frontier3_wiring(output)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--source-stage", default="frontier2")
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    summary = save_run(args.run_id, args.source_sha, args.source_stage,
                       Path(args.raw_dir), Path(args.output))
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
