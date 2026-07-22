#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import signal
import subprocess
import time
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path


GIB = 1024 ** 3
FRONTIER_ARCHIVES = Path(__file__).parent / "runs" / "2026-07-22-a" / "raw"


@dataclass(frozen=True)
class Task:
    stage: str
    orbit: int
    limit: int
    shard: int
    shards: int
    split: int = 15
    max_seen: int = 0

    @property
    def name(self) -> str:
        return f"{self.stage}-o{self.orbit}-l{self.limit}-s{self.shard:05d}-of-{self.shards}"


def frontier2_tasks() -> list[Task]:
    parents: list[dict[str, object]] = []
    archives = sorted(FRONTIER_ARCHIVES.glob("data-*.zip"))
    if len(archives) != 20:
        raise RuntimeError(f"expected 20 source artifacts, found {len(archives)}")
    for archive in archives:
        with zipfile.ZipFile(archive) as handle:
            manifest_name = next(
                (name for name in handle.namelist() if name.endswith("manifest.json")), None
            )
            if manifest_name is None:
                raise RuntimeError(f"manifest missing in {archive}")
            document = json.loads(handle.read(manifest_name))
        parents.extend(record for record in document["records"] if record["status"] == "capacity")
    parents.sort(key=lambda row: (int(row["limit"]), int(row["orbit"]), int(row["shard"])))
    if len(parents) != 785:
        raise RuntimeError(f"expected 785 capacity parents, found {len(parents)}")

    factor = 16
    refined_max_seen = 8_000_000
    tasks: list[Task] = []

    # Preserve the old split boundary. A child q refines parent p exactly when
    # q mod old_shards == p, so completed parts of the old run are never repeated.
    for child in range(factor):
        for parent in parents:
            old_shards = int(parent["shards"])
            tasks.append(Task(
                "r", int(parent["orbit"]), int(parent["limit"]),
                int(parent["shard"]) + old_shards * child,
                old_shards * factor, int(parent["split"]), refined_max_seen,
            ))

    # Advance in increasing support size. Limit 29 is a reserve queue so all
    # 80 virtual cores remain occupied if limit 28 completes unexpectedly early.
    for label, limit, shards, split in (
        ("c", 28, 1024, 16),
        ("d", 29, 2048, 17),
    ):
        for shard in range(shards):
            for orbit in range(8):
                tasks.append(Task(label, orbit, limit, shard, shards, split))
    return tasks


def all_tasks(stage: str) -> list[Task]:
    tasks: list[Task] = []
    if stage == "frontier2":
        return frontier2_tasks()
    if stage in {"frontier", "layer26"}:
        for orbit in (1, 2, 4, 5, 6, 7):
            tasks.extend(Task("a", orbit, 26, shard, 256) for shard in range(256))
    if stage in {"frontier", "layer27"}:
        for orbit in range(8):
            tasks.extend(Task("b", orbit, 27, shard, 256) for shard in range(256))
    return tasks


def meminfo() -> tuple[int, int]:
    values: dict[str, int] = {}
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        key, value, *_ = line.replace(":", "").split()
        values[key] = int(value) * 1024
    available = values.get("MemAvailable", 0)
    swap_used = values.get("SwapTotal", 0) - values.get("SwapFree", 0)
    return available, swap_used


def rss(pid: int) -> int:
    try:
        for line in Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except (FileNotFoundError, ProcessLookupError):
        pass
    return 0


def read_result(path: Path) -> tuple[str, dict[str, object], list[str]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        words = lines[0].split()
        value = lambda key: words[words.index(key) + 1]
        details: dict[str, object] = {
            "nodes": int(value("nodes")),
            "seen": int(value("seen")),
            "seconds": float(value("seconds")),
            "effective_max_seen": int(value("max_seen")),
        }
        return value("status"), details, lines[1:]
    except (FileNotFoundError, IndexError, ValueError):
        return "missing", {}, []


def stop_process(process: subprocess.Popen[str], hard: bool = False) -> None:
    if process.poll() is not None:
        return
    try:
        process.send_signal(signal.SIGKILL if hard else signal.SIGTERM)
    except ProcessLookupError:
        pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", type=int, default=0)
    parser.add_argument("--job-count", type=int, default=20)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--runtime-seconds", type=int, default=21_000)
    parser.add_argument("--task-seconds", type=int, default=3_600)
    parser.add_argument("--max-seen", type=int, default=32_000_000)
    parser.add_argument(
        "--stage", choices=("frontier", "layer26", "layer27", "frontier2"),
        default="frontier2",
    )
    parser.add_argument("--output", default="out")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not 0 <= args.job_id < args.job_count:
        parser.error("job-id must be smaller than job-count")
    tasks0 = all_tasks(args.stage)
    tasks = [task for index, task in enumerate(tasks0) if index % args.job_count == args.job_id]
    if args.dry_run:
        counts = [sum(1 for index in range(len(tasks0)) if index % args.job_count == job)
                  for job in range(args.job_count)]
        by_limit = {
            str(limit): sum(1 for task in tasks0 if task.limit == limit)
            for limit in sorted({task.limit for task in tasks0})
        }
        print(json.dumps({"total": len(tasks0), "per_job": counts, "by_limit": by_limit},
                         sort_keys=True))
        assert max(counts) - min(counts) <= 1
        return 0

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    deadline = start + args.runtime_seconds
    launch_margin = min(240, max(5, args.runtime_seconds // 16))
    shutdown_margin = min(180, max(3, args.runtime_seconds // 20))
    shutdown_grace = min(90, max(2, args.runtime_seconds // 50))
    pending = list(tasks)
    active: dict[int, tuple[Task, subprocess.Popen[str], object, Path, Path]] = {}
    records: list[dict[str, object]] = []
    technical_failure = False
    low_memory_strikes = 0
    resource_file = (output / "resources.tsv").open("w", encoding="utf-8", buffering=1)
    resource_file.write("elapsed_s\trss_bytes\tmem_available_bytes\tswap_used_bytes\tactive\tpending\n")
    record_file = (output / "records.jsonl").open("w", encoding="utf-8", buffering=1)

    def launch(task: Task) -> None:
        remaining = max(60, int(deadline - time.monotonic() - 180))
        task_seconds = min(args.task_seconds, remaining)
        result_path = output / f"{task.name}.txt"
        log_path = output / f"{task.name}.log"
        log_handle = log_path.open("w", encoding="utf-8")
        effective_max_seen = task.max_seen or args.max_seen
        command = [
            "./search", "--orbit", str(task.orbit), "--limit", str(task.limit),
            "--shard-count", str(task.shards), "--shard-index", str(task.shard),
            "--split-size", str(task.split), "--time-limit", str(task_seconds),
            "--max-seen", str(effective_max_seen), "--report-every", "0",
            "--output", str(result_path),
        ]
        process = subprocess.Popen(command, stdout=log_handle, stderr=subprocess.STDOUT, text=True)
        active[process.pid] = (task, process, log_handle, result_path, log_path)

    def finish(pid: int, expected_stop: bool = False) -> None:
        nonlocal technical_failure
        task, process, log_handle, result_path, log_path = active.pop(pid)
        if process.poll() is None:
            process.wait(timeout=10)
        log_handle.close()
        status, details, solutions = read_result(result_path)
        if expected_stop and status == "missing":
            status = "deadline_kill"
        record = asdict(task) | details | {
            "name": task.name,
            "returncode": process.returncode,
            "status": status,
            "solutions": solutions,
        }
        records.append(record)
        record_file.write(json.dumps(record, sort_keys=True) + "\n")
        failure = not expected_stop and (process.returncode != 0 or status == "missing")
        technical_failure = technical_failure or failure
        if not failure:
            result_path.unlink(missing_ok=True)
            log_path.unlink(missing_ok=True)

    try:
        while pending or active:
            now = time.monotonic()
            while pending and len(active) < args.workers and now < deadline - launch_margin:
                launch(pending.pop(0))

            time.sleep(5)
            available, swap_used = meminfo()
            total_rss = sum(rss(pid) for pid in active)
            resource_file.write(
                f"{time.monotonic() - start:.1f}\t{total_rss}\t{available}\t{swap_used}"
                f"\t{len(active)}\t{len(pending)}\n"
            )

            danger = total_rss > int(11.5 * GIB) or available < int(2.5 * GIB) or swap_used > GIB
            low_memory_strikes = low_memory_strikes + 1 if danger else 0
            if low_memory_strikes >= 3 and active:
                largest = max(active, key=rss)
                stop_process(active[largest][1])
                low_memory_strikes = 0

            finished = [pid for pid, (_, process, _, _, _) in active.items()
                        if process.poll() is not None]
            for pid in finished:
                finish(pid)

            if time.monotonic() >= deadline - shutdown_margin:
                for _, process, _, _, _ in active.values():
                    stop_process(process)
                grace = time.monotonic() + shutdown_grace
                while active and time.monotonic() < grace:
                    time.sleep(2)
                    finished = [pid for pid, (_, process, _, _, _) in active.items()
                                if process.poll() is not None]
                    for pid in finished:
                        finish(pid, expected_stop=True)
                for pid in list(active):
                    stop_process(active[pid][1], hard=True)
                for pid in list(active):
                    try:
                        active[pid][1].wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        pass
                    finish(pid, expected_stop=True)
                break
    finally:
        for pid in list(active):
            stop_process(active[pid][1], hard=True)
            try:
                active[pid][1].wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
            finish(pid, expected_stop=True)
        resource_file.close()
        record_file.close()

    completed_names = {str(record["name"]) for record in records}
    unstarted = [task.name for task in tasks if task.name not in completed_names]
    summary = {
        "job_id": args.job_id,
        "job_count": args.job_count,
        "stage": args.stage,
        "elapsed_seconds": time.monotonic() - start,
        "assigned": len(tasks),
        "recorded": len(records),
        "unstarted": unstarted,
        "counts": {
            status: sum(1 for record in records if record["status"] == status)
            for status in sorted({str(record["status"]) for record in records})
        },
        "limits": {
            str(limit): sum(1 for record in records if record["limit"] == limit)
            for limit in sorted({int(record["limit"]) for record in records})
        },
    }
    (output / "manifest.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n",
                                           encoding="utf-8")
    print(json.dumps(summary["counts"], sort_keys=True), flush=True)
    return 1 if technical_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
