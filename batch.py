#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path


GIB = 1024 ** 3


@dataclass(frozen=True)
class Task:
    stage: str
    orbit: int
    limit: int
    shard: int
    shards: int
    split: int = 15

    @property
    def name(self) -> str:
        return f"{self.stage}-o{self.orbit}-l{self.limit}-s{self.shard:03d}-of-{self.shards}"


def all_tasks(stage: str) -> list[Task]:
    tasks: list[Task] = []
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


def parse_status(path: Path) -> str:
    try:
        first = path.read_text(encoding="utf-8").splitlines()[0].split()
        return first[first.index("status") + 1]
    except (FileNotFoundError, IndexError, ValueError):
        return "missing"


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
    parser.add_argument("--runtime-seconds", type=int, default=20_400)
    parser.add_argument("--task-seconds", type=int, default=3_600)
    parser.add_argument("--max-seen", type=int, default=8_000_000)
    parser.add_argument("--stage", choices=("frontier", "layer26", "layer27"), default="frontier")
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
        print(json.dumps({"total": len(tasks0), "per_job": counts}, sort_keys=True))
        assert max(counts) - min(counts) <= 1
        return 0

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    deadline = start + args.runtime_seconds
    pending = list(tasks)
    active: dict[int, tuple[Task, subprocess.Popen[str], object, Path, Path]] = {}
    records: list[dict[str, object]] = []
    technical_failure = False
    low_memory_strikes = 0
    resource_path = output / "resources.tsv"
    resource_file = resource_path.open("w", encoding="utf-8", buffering=1)
    resource_file.write("elapsed_s\trss_bytes\tmem_available_bytes\tswap_used_bytes\tactive\tpending\n")

    def launch(task: Task) -> None:
        remaining = max(60, int(deadline - time.monotonic() - 180))
        task_seconds = min(args.task_seconds, remaining)
        result_path = output / f"{task.name}.txt"
        log_path = output / f"{task.name}.log"
        log_handle = log_path.open("w", encoding="utf-8")
        command = [
            "./search", "--orbit", str(task.orbit), "--limit", str(task.limit),
            "--shard-count", str(task.shards), "--shard-index", str(task.shard),
            "--split-size", str(task.split), "--time-limit", str(task_seconds),
            "--max-seen", str(args.max_seen), "--report-every", "0",
            "--output", str(result_path),
        ]
        process = subprocess.Popen(command, stdout=log_handle, stderr=subprocess.STDOUT, text=True)
        active[process.pid] = (task, process, log_handle, result_path, log_path)

    try:
        while pending or active:
            now = time.monotonic()
            while pending and len(active) < args.workers and now < deadline - 240:
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
                task, process, log_handle, result_path, log_path = active.pop(pid)
                log_handle.close()
                status = parse_status(result_path)
                record = asdict(task) | {
                    "name": task.name,
                    "returncode": process.returncode,
                    "status": status,
                    "result": result_path.name,
                    "log": log_path.name,
                }
                records.append(record)
                if process.returncode != 0 or status == "missing":
                    technical_failure = True

            if time.monotonic() >= deadline - 180:
                for _, process, _, _, _ in active.values():
                    stop_process(process)
                limit = time.monotonic() + 90
                while active and time.monotonic() < limit:
                    time.sleep(2)
                    finished = [pid for pid, (_, process, _, _, _) in active.items()
                                if process.poll() is not None]
                    for pid in finished:
                        task, process, log_handle, result_path, log_path = active.pop(pid)
                        log_handle.close()
                        status = parse_status(result_path)
                        records.append(asdict(task) | {
                            "name": task.name, "returncode": process.returncode,
                            "status": status, "result": result_path.name, "log": log_path.name,
                        })
                for _, process, _, _, _ in active.values():
                    stop_process(process, hard=True)
                break
    finally:
        for _, process, log_handle, _, _ in active.values():
            stop_process(process, hard=True)
            log_handle.close()
        resource_file.close()

    completed_names = {str(record["name"]) for record in records}
    unstarted = [task.name for task in tasks if task.name not in completed_names]
    summary = {
        "job_id": args.job_id,
        "job_count": args.job_count,
        "stage": args.stage,
        "elapsed_seconds": time.monotonic() - start,
        "assigned": len(tasks),
        "records": records,
        "unstarted": unstarted,
        "counts": {
            status: sum(1 for record in records if record["status"] == status)
            for status in sorted({str(record["status"]) for record in records})
        },
    }
    (output / "manifest.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n",
                                           encoding="utf-8")
    print(json.dumps(summary["counts"], sort_keys=True), flush=True)
    return 1 if technical_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
