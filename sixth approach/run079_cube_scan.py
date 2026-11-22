#!/usr/bin/env python3
"""Run and strictly collect one neutral, exhaustive bounded CNF cube scan."""

from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time


def canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def seal(payload):
    result = dict(payload)
    result.pop("canonical_sha256", None)
    result["canonical_sha256"] = hashlib.sha256(canonical_bytes(result)).hexdigest()
    return result


def check_seal(payload):
    unsigned = dict(payload)
    claimed = unsigned.pop("canonical_sha256", None)
    if claimed != hashlib.sha256(canonical_bytes(unsigned)).hexdigest():
        raise ValueError("canonical payload mismatch")
    return claimed


def atomic_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def load_spec(path):
    path = Path(path)
    spec = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema": "neutral-exhaustive-cube-scan-v1",
        "run_id": "run-079",
        "physical_jobs": 19,
        "logical_workers_per_job": 4,
        "lane_count": 76,
        "max_parallel": 19,
        "single_threaded_solver_per_worker": True,
        "cube_depth": 12,
        "cube_count": 4096,
        "variable_count": 30053,
        "clause_count": 132727,
        "input_sha256": "564abcadb9eb164a6a75bef84fddaefc46dbb25076277a693884696b2df55cce",
        "solver_seconds_per_cube": 55,
    }
    for key, value in required.items():
        if spec.get(key) != value:
            raise ValueError(f"immutable specification mismatch: {key}")
    cube_variables = spec.get("cube_variables")
    if (
        not isinstance(cube_variables, list)
        or len(cube_variables) != spec["cube_depth"]
        or len(set(cube_variables)) != len(cube_variables)
        or any(not isinstance(value, int) or not 1 <= value <= spec["variable_count"]
               for value in cube_variables)
    ):
        raise ValueError("invalid cube variables")
    input_path = path.parent / spec.get("input_file", "")
    if not input_path.is_file() or sha256_file(input_path) != spec["input_sha256"]:
        raise ValueError("input identity mismatch")
    if spec.get("script_sha256") != sha256_file(__file__):
        raise ValueError("worker script identity mismatch")
    spec["_path"] = str(path.resolve())
    spec["_input_path"] = str(input_path.resolve())
    spec["_file_sha256"] = sha256_file(path)
    return spec


def read_dimacs(path, expected_variables=None, expected_clauses=None):
    raw = Path(path).read_bytes()
    lines = raw.splitlines(keepends=True)
    header_index = None
    variable_count = clause_count = None
    clauses = []
    for index, raw_line in enumerate(lines):
        line = raw_line.decode("ascii").strip()
        if not line or line.startswith("c"):
            continue
        if line.startswith("p "):
            if header_index is not None:
                raise ValueError("duplicate DIMACS header")
            parts = line.split()
            if len(parts) != 4 or parts[:2] != ["p", "cnf"]:
                raise ValueError("invalid DIMACS header")
            header_index = index
            variable_count, clause_count = map(int, parts[2:])
            continue
        values = tuple(map(int, line.split()))
        if not values or values[-1] != 0 or any(value == 0 for value in values[:-1]):
            raise ValueError("invalid DIMACS clause")
        clauses.append(values[:-1])
    if header_index is None or len(clauses) != clause_count:
        raise ValueError("DIMACS census mismatch")
    if expected_variables is not None and variable_count != expected_variables:
        raise ValueError("DIMACS variable count mismatch")
    if expected_clauses is not None and clause_count != expected_clauses:
        raise ValueError("DIMACS clause count mismatch")
    return raw, lines, header_index, variable_count, tuple(clauses)


def cube_literals(spec, cube_id):
    if not 0 <= cube_id < spec["cube_count"]:
        raise ValueError("cube id outside partition")
    return tuple(
        variable if (cube_id >> bit) & 1 else -variable
        for bit, variable in enumerate(spec["cube_variables"])
    )


def lane_cubes(spec, lane):
    if not 0 <= lane < spec["lane_count"]:
        raise ValueError("lane outside matrix")
    return tuple(range(lane, spec["cube_count"], spec["lane_count"]))


def emit_cube(lines, header_index, variables, clauses, literals, output):
    output = Path(output)
    with output.open("wb") as stream:
        for index, line in enumerate(lines):
            if index == header_index:
                stream.write(f"p cnf {variables} {clauses + len(literals)}\n".encode("ascii"))
            else:
                stream.write(line if line.endswith((b"\n", b"\r")) else line + b"\n")
        for literal in literals:
            stream.write(f"{literal} 0\n".encode("ascii"))


def parse_model(text, variable_count):
    values = {}
    for line in text.splitlines():
        if not line.startswith("v"):
            continue
        for token in line[1:].split():
            literal = int(token)
            if literal:
                variable = abs(literal)
                if variable > variable_count or variable in values:
                    raise ValueError("invalid or duplicate model literal")
                values[variable] = literal > 0
    if len(values) != variable_count:
        raise ValueError("solver model is incomplete")
    return values


def replay_model(clauses, literals, assignment):
    if any(not assignment[abs(literal)] if literal > 0 else assignment[abs(literal)]
           for literal in literals):
        raise ValueError("model violates cube assumptions")
    for clause in clauses:
        if not any(
            assignment[abs(literal)] if literal > 0 else not assignment[abs(literal)]
            for literal in clause
        ):
            raise ValueError("model violates source CNF")


def run_cube(spec, cube_id, base, cadical, seconds):
    raw, lines, header_index, variable_count, clauses = base
    del raw
    literals = cube_literals(spec, cube_id)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix=f"cube-{cube_id:04d}-") as temporary:
        cube_path = Path(temporary) / "input.cnf"
        emit_cube(
            lines, header_index, variable_count, len(clauses), literals, cube_path
        )
        try:
            process = subprocess.run(
                [cadical, f"--seed={79000001 + cube_id}", str(cube_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=seconds,
                check=False,
            )
            output = process.stdout
            code = process.returncode
        except subprocess.TimeoutExpired as error:
            output = (error.stdout or "")
            if isinstance(output, bytes):
                output = output.decode("utf-8", errors="replace")
            code = 124
    elapsed = time.monotonic() - started
    record = {
        "cube_id": cube_id,
        "cube_literals": list(literals),
        "solver_exit": code,
        "wall_seconds": elapsed,
        "solver_output_tail": output[-4000:],
    }
    try:
        if code == 10:
            assignment = parse_model(output, variable_count)
            replay_model(clauses, literals, assignment)
            record.update({
                "state": "SAT_REPLAYED",
                "true_variables": [
                    variable for variable in range(1, variable_count + 1)
                    if assignment[variable]
                ],
                "support_true_variables": [
                    variable for variable in range(1, 136) if assignment[variable]
                ],
                "all_source_clauses_replayed": True,
            })
        elif code == 20:
            record["state"] = "UNSAT_UNCERTIFIED"
        elif code == 124:
            record["state"] = "TIMEOUT"
        else:
            record["state"] = "TECHNICAL_ERROR"
    except Exception as error:  # preserve exact diagnostic in the lane artifact
        record["state"] = "TECHNICAL_ERROR"
        record["replay_error"] = f"{type(error).__name__}: {error}"
    return record


def lane_payload(spec, lane, records, complete):
    return seal({
        "schema": "neutral-exhaustive-cube-lane-v1",
        "run_id": spec["run_id"],
        "spec_sha256": spec["_file_sha256"],
        "input_sha256": spec["input_sha256"],
        "lane": lane,
        "assigned_cube_ids": list(lane_cubes(spec, lane)),
        "records": records,
        "record_count": len(records),
        "complete": complete,
        "state_histogram": dict(sorted(Counter(
            record["state"] for record in records
        ).items())),
    })


def command_contract(args):
    spec = load_spec(args.spec)
    read_dimacs(
        spec["_input_path"], spec["variable_count"], spec["clause_count"]
    )
    all_ids = [cube for lane in range(spec["lane_count"])
               for cube in lane_cubes(spec, lane)]
    if sorted(all_ids) != list(range(spec["cube_count"])):
        raise ValueError("lane partition is not exact")
    print(json.dumps({
        "accepted": True,
        "spec_sha256": spec["_file_sha256"],
        "input_sha256": spec["input_sha256"],
        "cube_count": spec["cube_count"],
        "lane_count": spec["lane_count"],
        "lane_size_histogram": dict(sorted(Counter(
            len(lane_cubes(spec, lane)) for lane in range(spec["lane_count"])
        ).items())),
    }, sort_keys=True))


def command_self_test(args):
    spec = load_spec(args.spec)
    signatures = {cube_literals(spec, cube) for cube in range(spec["cube_count"])}
    if len(signatures) != spec["cube_count"]:
        raise ValueError("duplicate cubes")
    for assignment in range(1 << spec["cube_depth"]):
        literals = cube_literals(spec, assignment)
        recovered = sum((literal > 0) << bit for bit, literal in enumerate(literals))
        if recovered != assignment:
            raise ValueError("cube coverage replay failed")
    print(json.dumps({
        "accepted": True,
        "assignments_replayed": 1 << spec["cube_depth"],
        "unique_cube_signatures": len(signatures),
    }, sort_keys=True))


def command_worker(args):
    spec = load_spec(args.spec)
    base = read_dimacs(
        spec["_input_path"], spec["variable_count"], spec["clause_count"]
    )
    assigned = lane_cubes(spec, args.lane)
    if args.smoke:
        assigned = assigned[:1]
    seconds = 1 if args.smoke else spec["solver_seconds_per_cube"]
    records = []
    atomic_json(args.output, lane_payload(spec, args.lane, records, False))
    for cube_id in assigned:
        records.append(run_cube(spec, cube_id, base, args.cadical, seconds))
        atomic_json(
            args.output,
            lane_payload(spec, args.lane, records, len(records) == len(assigned)),
        )
    if any(record["state"] == "TECHNICAL_ERROR" for record in records):
        raise SystemExit(2)


def validate_lane(spec, payload, lane, allow_partial=False):
    check_seal(payload)
    expected = list(lane_cubes(spec, lane))
    records = payload.get("records", [])
    ids = [record.get("cube_id") for record in records]
    if (
        payload.get("schema") != "neutral-exhaustive-cube-lane-v1"
        or payload.get("run_id") != spec["run_id"]
        or payload.get("spec_sha256") != spec["_file_sha256"]
        or payload.get("input_sha256") != spec["input_sha256"]
        or payload.get("lane") != lane
        or payload.get("assigned_cube_ids") != expected
        or payload.get("record_count") != len(records)
        or ids != expected[:len(ids)]
        or len(ids) != len(set(ids))
        or (not allow_partial and (ids != expected or payload.get("complete") is not True))
    ):
        raise ValueError(f"lane {lane} contract mismatch")
    for record in records:
        state = record.get("state")
        code = record.get("solver_exit")
        if (
            not isinstance(record.get("wall_seconds"), (int, float))
            or record["wall_seconds"] < 0
            or not isinstance(record.get("solver_output_tail"), str)
            or (state == "SAT_REPLAYED" and (
                code != 10
                or record.get("all_source_clauses_replayed") is not True
                or not isinstance(record.get("true_variables"), list)
            ))
            or (state == "UNSAT_UNCERTIFIED" and code != 20)
            or (state == "TIMEOUT" and code != 124)
            or (state == "TECHNICAL_ERROR" and code in (10, 20, 124))
            or state not in {
                "SAT_REPLAYED", "UNSAT_UNCERTIFIED", "TIMEOUT", "TECHNICAL_ERROR"
            }
        ):
            raise ValueError(f"lane {lane} record-state contract mismatch")
    return records


def command_validate_group(args):
    spec = load_spec(args.spec)
    histogram = Counter()
    lanes = []
    for slot in range(spec["logical_workers_per_job"]):
        lane = args.group * spec["logical_workers_per_job"] + slot
        path = args.input_root / f"lane-{lane:03d}" / "result.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = validate_lane(spec, payload, lane)
        histogram.update(record["state"] for record in records)
        lanes.append(lane)
    summary = seal({
        "schema": "neutral-exhaustive-cube-group-v1",
        "run_id": spec["run_id"],
        "group": args.group,
        "lanes": lanes,
        "state_histogram": dict(sorted(histogram.items())),
    })
    atomic_json(args.input_root / "group-summary.json", summary)
    if histogram["TECHNICAL_ERROR"]:
        raise SystemExit(2)


def command_collect(args):
    spec = load_spec(args.spec)
    _raw, _lines, _header, _variables, clauses = read_dimacs(
        spec["_input_path"], spec["variable_count"], spec["clause_count"]
    )
    lane_payloads = {}
    for path in args.input_root.rglob("result.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema") != "neutral-exhaustive-cube-lane-v1":
            continue
        lane = payload.get("lane")
        if lane in lane_payloads:
            raise ValueError(f"duplicate lane {lane}")
        lane_payloads[lane] = payload
    all_records = []
    missing_lanes = []
    invalid_lanes = []
    for lane in range(spec["lane_count"]):
        payload = lane_payloads.get(lane)
        if payload is None:
            missing_lanes.append(lane)
            continue
        try:
            records = validate_lane(spec, payload, lane, allow_partial=True)
        except Exception as error:
            invalid_lanes.append({"lane": lane, "error": str(error)})
            continue
        all_records.extend(records)
    by_cube = {}
    duplicate_cubes = []
    replay_failures = []
    for record in all_records:
        cube_id = record["cube_id"]
        if cube_id in by_cube:
            duplicate_cubes.append(cube_id)
            continue
        by_cube[cube_id] = record
        if record.get("cube_literals") != list(cube_literals(spec, cube_id)):
            replay_failures.append({"cube_id": cube_id, "error": "cube literals"})
            continue
        if record.get("state") == "SAT_REPLAYED":
            truth = set(record.get("true_variables", []))
            if any(not isinstance(value, int) or not 1 <= value <= spec["variable_count"]
                   for value in truth):
                replay_failures.append({"cube_id": cube_id, "error": "model range"})
                continue
            assignment = {
                variable: variable in truth
                for variable in range(1, spec["variable_count"] + 1)
            }
            try:
                replay_model(clauses, cube_literals(spec, cube_id), assignment)
            except Exception as error:
                replay_failures.append({"cube_id": cube_id, "error": str(error)})
    missing_cubes = sorted(set(range(spec["cube_count"])) - set(by_cube))
    histogram = Counter(record.get("state", "MISSING_STATE") for record in by_cube.values())
    technical_complete = not (
        missing_lanes or invalid_lanes or duplicate_cubes or missing_cubes
        or replay_failures or histogram["TECHNICAL_ERROR"] or histogram["MISSING_STATE"]
    )
    if histogram["SAT_REPLAYED"]:
        conclusion = "SAT_WITNESS_REPLAYED"
    elif not technical_complete:
        conclusion = "TECHNICALLY_INCOMPLETE"
    elif histogram["TIMEOUT"]:
        conclusion = "OPEN_BOUNDED_RESIDUE"
    elif histogram["UNSAT_UNCERTIFIED"] == spec["cube_count"]:
        conclusion = "UNCERTIFIED_UNSAT_SCAN"
    else:
        conclusion = "UNCLASSIFIED"
    summary = seal({
        "schema": "neutral-exhaustive-cube-collection-v1",
        "run_id": spec["run_id"],
        "workflow_run": args.workflow_run,
        "source_sha": args.source_sha,
        "spec_sha256": spec["_file_sha256"],
        "input_sha256": spec["input_sha256"],
        "cube_count": spec["cube_count"],
        "record_count": len(by_cube),
        "state_histogram": dict(sorted(histogram.items())),
        "missing_lanes": missing_lanes,
        "invalid_lanes": invalid_lanes,
        "missing_cube_ids": missing_cubes,
        "duplicate_cube_ids": sorted(set(duplicate_cubes)),
        "sat_replay_failures": replay_failures,
        "technical_complete": technical_complete,
        "conclusion": conclusion,
        "proof_boundary": (
            "UNSAT cube exits are bounded diagnostics without proof certificates; "
            "only SAT models receive mathematical status in this scan"
        ),
    })
    args.output_dir.mkdir(parents=True, exist_ok=True)
    atomic_json(args.output_dir / "summary.json", summary)
    compact_records = []
    for cube_id in sorted(by_cube):
        record = dict(by_cube[cube_id])
        full_assignment = record.pop("true_variables", None)
        if full_assignment is not None:
            record["true_variables_sha256"] = hashlib.sha256(
                canonical_bytes(full_assignment)
            ).hexdigest()
        compact_records.append(record)
    catalogue = {
        "schema": "neutral-exhaustive-cube-catalogue-v1",
        "summary_canonical_sha256": summary["canonical_sha256"],
        "records": compact_records,
    }
    with (args.output_dir / "catalogue.json.gz").open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as stream:
            stream.write(canonical_bytes(catalogue))
    print(json.dumps({
        "technical_complete": technical_complete,
        "conclusion": conclusion,
        "state_histogram": dict(sorted(histogram.items())),
        "summary_canonical_sha256": summary["canonical_sha256"],
    }, sort_keys=True))
    if not technical_complete:
        raise SystemExit(2)


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("contract", "self-test"):
        child = subparsers.add_parser(name)
        child.add_argument("--spec", type=Path, required=True)
    worker = subparsers.add_parser("worker")
    worker.add_argument("--spec", type=Path, required=True)
    worker.add_argument("--lane", type=int, required=True)
    worker.add_argument("--output", type=Path, required=True)
    worker.add_argument("--cadical", default="cadical")
    worker.add_argument("--smoke", action="store_true")
    group = subparsers.add_parser("validate-group")
    group.add_argument("--spec", type=Path, required=True)
    group.add_argument("--group", type=int, required=True)
    group.add_argument("--input-root", type=Path, required=True)
    collect = subparsers.add_parser("collect")
    collect.add_argument("--spec", type=Path, required=True)
    collect.add_argument("--input-root", type=Path, required=True)
    collect.add_argument("--output-dir", type=Path, required=True)
    collect.add_argument("--workflow-run", required=True)
    collect.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    {
        "contract": command_contract,
        "self-test": command_self_test,
        "worker": command_worker,
        "validate-group": command_validate_group,
        "collect": command_collect,
    }[args.command](args)


if __name__ == "__main__":
    main()
