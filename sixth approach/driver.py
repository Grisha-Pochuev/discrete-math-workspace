#!/usr/bin/env python3
"""Strict validation and collection for the neutral run-000 worker protocol."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_ORBITS = 1108
EXPECTED_TRIPLES = 23_019_264
ASSIGNMENTS_PER_ORBIT = 59_049


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top level must be an object")
    return value


def validate_worker(
    data: dict[str, Any],
    *,
    expected_worker_count: int | None = None,
    require_success: bool = True,
) -> None:
    if data.get("schema_version") != 1 or data.get("series") != "run-000":
        raise ValueError("unexpected worker schema or series")
    worker_id = data.get("worker_id")
    worker_count = data.get("worker_count")
    if not isinstance(worker_id, int) or not isinstance(worker_count, int):
        raise ValueError("worker partition fields must be integers")
    if worker_count <= 0 or worker_id < 0 or worker_id >= worker_count:
        raise ValueError("invalid worker partition")
    if expected_worker_count is not None and worker_count != expected_worker_count:
        raise ValueError(f"worker {worker_id}: worker_count={worker_count}, expected {expected_worker_count}")
    if require_success and data.get("technical_status") != "SUCCESS":
        raise ValueError(f"worker {worker_id}: status is {data.get('technical_status')!r}")

    exact = data.get("exact")
    frontier = data.get("frontier")
    if not isinstance(exact, dict) or not isinstance(frontier, dict):
        raise ValueError(f"worker {worker_id}: missing result sections")
    if exact.get("order") != 10 or exact.get("allowed_matchings") != 544:
        raise ValueError(f"worker {worker_id}: exact constants mismatch")
    if exact.get("orbit_count") != EXPECTED_ORBITS:
        raise ValueError(f"worker {worker_id}: orbit count mismatch")
    if exact.get("labelled_factor_triples") != EXPECTED_TRIPLES:
        raise ValueError(f"worker {worker_id}: factor triple count mismatch")
    digest = exact.get("orbit_digest")
    if not isinstance(digest, str) or not digest.startswith("0x") or len(digest) != 18:
        raise ValueError(f"worker {worker_id}: malformed orbit digest")

    assigned = exact.get("assigned_orbits")
    completed = exact.get("completed_orbits")
    expected_assigned = list(range(worker_id, EXPECTED_ORBITS, worker_count))
    if assigned != expected_assigned:
        raise ValueError(f"worker {worker_id}: assigned-orbit partition mismatch")
    if require_success and completed != assigned:
        raise ValueError(f"worker {worker_id}: incomplete exact shard")
    if not isinstance(completed, list) or len(completed) != len(set(completed)):
        raise ValueError(f"worker {worker_id}: duplicate completed orbit")
    if require_success and exact.get("assignments_checked") != len(assigned) * ASSIGNMENTS_PER_ORBIT:
        raise ValueError(f"worker {worker_id}: exact assignment count mismatch")

    integer_fields = (
        "assignments_checked",
        "trap_cases",
        "h_zero_cases",
        "threshold_violations",
        "minimum_full_safe",
    )
    for field in integer_fields:
        if not isinstance(exact.get(field), int):
            raise ValueError(f"worker {worker_id}: exact.{field} is not an integer")
    for field in ("systems_checked", "assignments_checked", "trap_cases", "threshold_violations", "minimum_full_safe"):
        if not isinstance(frontier.get(field), int):
            raise ValueError(f"worker {worker_id}: frontier.{field} is not an integer")
    for key in ("h_zero_records", "equality_records"):
        if not isinstance(exact.get(key), list):
            raise ValueError(f"worker {worker_id}: exact.{key} is not a list")
    if not isinstance(frontier.get("records"), list):
        raise ValueError(f"worker {worker_id}: frontier.records is not a list")


def command_verify_worker(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = read_json(path)
    validate_worker(data, expected_worker_count=args.worker_count, require_success=True)
    exact = data["exact"]
    frontier = data["frontier"]
    print(json.dumps({
        "status": "SUCCESS",
        "worker_id": data["worker_id"],
        "completed_orbits": len(exact["completed_orbits"]),
        "exact_assignments": exact["assignments_checked"],
        "frontier_assignments": frontier["assignments_checked"],
    }, sort_keys=True))
    return 0


def discover_workers(root: Path, expected_workers: int) -> list[tuple[Path, dict[str, Any]]]:
    candidates = sorted(root.rglob("worker-*.json"))
    by_id: dict[int, tuple[Path, dict[str, Any]]] = {}
    for path in candidates:
        data = read_json(path)
        validate_worker(data, expected_worker_count=expected_workers, require_success=True)
        worker_id = data["worker_id"]
        if worker_id in by_id:
            raise ValueError(f"duplicate worker id {worker_id}: {by_id[worker_id][0]} and {path}")
        by_id[worker_id] = (path, data)
    expected_ids = set(range(expected_workers))
    if set(by_id) != expected_ids:
        missing = sorted(expected_ids - set(by_id))
        extra = sorted(set(by_id) - expected_ids)
        raise ValueError(f"worker set mismatch; missing={missing}, extra={extra}")
    return [by_id[index] for index in range(expected_workers)]


def numeric_sum(workers: list[dict[str, Any]], section: str, field: str) -> int:
    return sum(worker[section][field] for worker in workers)


def write_checksums(directory: Path) -> None:
    files = sorted(path for path in directory.iterdir() if path.is_file() and path.name != "checksums.sha256")
    lines = []
    for path in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.name}")
    (directory / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def command_collect(args: argparse.Namespace) -> int:
    root = Path(args.input_root)
    output = Path(args.output_dir)
    discovered = discover_workers(root, args.expected_workers)
    workers = [data for _, data in discovered]

    digests = {worker["exact"]["orbit_digest"] for worker in workers}
    if len(digests) != 1:
        raise ValueError(f"workers disagree on orbit digest: {sorted(digests)}")

    coverage: dict[int, int] = {}
    for worker in workers:
        for orbit in worker["exact"]["completed_orbits"]:
            if orbit in coverage:
                raise ValueError(f"orbit {orbit} completed by workers {coverage[orbit]} and {worker['worker_id']}")
            coverage[orbit] = worker["worker_id"]
    if set(coverage) != set(range(EXPECTED_ORBITS)):
        missing = sorted(set(range(EXPECTED_ORBITS)) - set(coverage))
        raise ValueError(f"exact coverage incomplete: {missing}")

    exact_assignments = numeric_sum(workers, "exact", "assignments_checked")
    if exact_assignments != EXPECTED_ORBITS * ASSIGNMENTS_PER_ORBIT:
        raise ValueError("aggregate exact assignment count mismatch")

    exact_minima = [worker["exact"]["minimum_full_safe"] for worker in workers if worker["exact"]["minimum_full_safe"] >= 0]
    frontier_minima = [worker["frontier"]["minimum_full_safe"] for worker in workers if worker["frontier"]["minimum_full_safe"] >= 0]
    h_zero_records = [record for worker in workers for record in worker["exact"]["h_zero_records"]]
    equality_records = [record for worker in workers for record in worker["exact"]["equality_records"]]
    frontier_records = [record for worker in workers for record in worker["frontier"]["records"]]
    frontier_records.sort(key=lambda record: (record["order"], record["full_safe"], record["h_safe"], -record["trap_count"]))

    summary = {
        "schema_version": 1,
        "series": "run-000",
        "run_id": str(args.run_id),
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "accepted": True,
        "acceptance_scope": "technical completeness of the declared computation",
        "worker_count": args.expected_workers,
        "worker_status_counts": {"SUCCESS": args.expected_workers},
        "exact": {
            "order": 10,
            "allowed_matchings": 544,
            "orbit_count": EXPECTED_ORBITS,
            "orbit_digest": next(iter(digests)),
            "labelled_factor_triples": EXPECTED_TRIPLES,
            "assignments_checked": exact_assignments,
            "trap_cases": numeric_sum(workers, "exact", "trap_cases"),
            "h_zero_cases": numeric_sum(workers, "exact", "h_zero_cases"),
            "threshold_violations": numeric_sum(workers, "exact", "threshold_violations"),
            "minimum_full_safe": min(exact_minima),
            "retained_h_zero_records": len(h_zero_records),
            "retained_equality_records": len(equality_records),
        },
        "frontier": {
            "orders": sorted({worker["frontier"]["order"] for worker in workers}),
            "systems_checked": numeric_sum(workers, "frontier", "systems_checked"),
            "assignments_checked": numeric_sum(workers, "frontier", "assignments_checked"),
            "trap_cases": numeric_sum(workers, "frontier", "trap_cases"),
            "threshold_violations": numeric_sum(workers, "frontier", "threshold_violations"),
            "minimum_full_safe": min(frontier_minima) if frontier_minima else -1,
            "retained_records": len(frontier_records),
        },
    }

    output.mkdir(parents=True, exist_ok=False)
    source_spec = Path(__file__).resolve().parent / "specs" / "run-000-structural-frontier.json"
    shutil.copy2(source_spec, output / source_spec.name)
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    (output / "selected-records.json").write_text(
        json.dumps({
            "h_zero_records": h_zero_records,
            "equality_records": equality_records,
            "frontier_records": frontier_records,
        }, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    with gzip.open(output / "worker-results.json.gz", "wt", encoding="utf-8", newline="\n", compresslevel=9) as handle:
        json.dump(workers, handle, separators=(",", ":"), sort_keys=True)
        handle.write("\n")
    write_checksums(output)

    if args.control:
        control_path = Path(args.control)
        control = read_json(control_path)
        control.update({
            "enabled": False,
            "status": "run_000_accepted",
            "completed_runs": int(control.get("completed_runs", 0)) + 1,
            "last_run_id": str(args.run_id),
            "last_archive": output.as_posix(),
            "notes": "Accepted after strict worker, digest, and exact-coverage validation.",
        })
        control_path.write_text(json.dumps(control, indent=2) + "\n", encoding="utf-8", newline="\n")

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify = subparsers.add_parser("verify-worker")
    verify.add_argument("path")
    verify.add_argument("--worker-count", type=int, required=True)
    verify.set_defaults(function=command_verify_worker)

    collect = subparsers.add_parser("collect")
    collect.add_argument("--input-root", required=True)
    collect.add_argument("--output-dir", required=True)
    collect.add_argument("--expected-workers", type=int, required=True)
    collect.add_argument("--run-id", required=True)
    collect.add_argument("--control")
    collect.set_defaults(function=command_collect)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.function(args)
    except Exception as error:  # collector failures must be concise and non-silent
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
