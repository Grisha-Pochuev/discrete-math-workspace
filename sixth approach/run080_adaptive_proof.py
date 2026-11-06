#!/usr/bin/env python3
"""Produce and strictly collect an adaptive exact-CNF proof cover."""

from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
import os
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
        "schema": "neutral-adaptive-proof-cover-v1",
        "run_id": "run-080",
        "physical_jobs": 19,
        "logical_workers_per_job": 4,
        "lane_count": 76,
        "max_parallel": 19,
        "single_threaded_solver_per_worker": True,
        "root_depth": 7,
        "maximum_depth": 12,
        "root_count": 128,
        "leaf_count": 4096,
        "variable_count": 30053,
        "clause_count": 132727,
        "input_sha256": "564abcadb9eb164a6a75bef84fddaefc46dbb25076277a693884696b2df55cce",
        "solver_seconds_internal_node": 30,
        "solver_seconds_leaf": 90,
        "checker_seconds": 180,
        "maximum_proof_uncompressed_bytes": 2147483648,
        "maximum_proof_compressed_bytes": 134217728,
        "maximum_lane_compressed_bytes": 134217728,
    }
    for key, value in required.items():
        if spec.get(key) != value:
            raise ValueError(f"immutable specification mismatch: {key}")
    variables = spec.get("partition_variables")
    if (
        not isinstance(variables, list)
        or len(variables) != spec["maximum_depth"]
        or len(set(variables)) != len(variables)
        or any(not isinstance(value, int) or not 1 <= value <= spec["variable_count"]
               for value in variables)
    ):
        raise ValueError("invalid partition variables")
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
    lines = Path(path).read_bytes().splitlines(keepends=True)
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
            fields = line.split()
            if len(fields) != 4 or fields[:2] != ["p", "cnf"]:
                raise ValueError("invalid DIMACS header")
            header_index = index
            variable_count, clause_count = map(int, fields[2:])
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
    return lines, header_index, variable_count, tuple(clauses)


def prefix_literals(spec, depth, prefix):
    if not spec["root_depth"] <= depth <= spec["maximum_depth"]:
        raise ValueError("prefix depth outside contract")
    if not 0 <= prefix < (1 << depth):
        raise ValueError("prefix value outside depth")
    return tuple(
        variable if (prefix >> bit) & 1 else -variable
        for bit, variable in enumerate(spec["partition_variables"][:depth])
    )


def lane_roots(spec, lane):
    if not 0 <= lane < spec["lane_count"]:
        raise ValueError("lane outside matrix")
    return tuple(range(lane, spec["root_count"], spec["lane_count"]))


def node_name(depth, prefix):
    return f"d{depth:02d}-p{prefix:04d}"


def emit_prefix_cnf(lines, header_index, variables, clause_count, literals, output):
    with Path(output).open("wb") as stream:
        for index, line in enumerate(lines):
            if index == header_index:
                stream.write(
                    f"p cnf {variables} {clause_count + len(literals)}\n".encode("ascii")
                )
            else:
                stream.write(line if line.endswith((b"\n", b"\r")) else line + b"\n")
        for literal in literals:
            stream.write(f"{literal} 0\n".encode("ascii"))


def parse_model(text, variable_count):
    assignment = {}
    for line in text.splitlines():
        if not line.startswith("v"):
            continue
        for token in line[1:].split():
            literal = int(token)
            if not literal:
                continue
            variable = abs(literal)
            if variable > variable_count or variable in assignment:
                raise ValueError("invalid or duplicate model literal")
            assignment[variable] = literal > 0
    if len(assignment) != variable_count:
        raise ValueError("solver model is incomplete")
    return assignment


def replay_model(clauses, literals, assignment):
    for literal in literals:
        if assignment[abs(literal)] != (literal > 0):
            raise ValueError("model violates prefix assumptions")
    for clause in clauses:
        if not any(
            assignment[abs(literal)] if literal > 0 else not assignment[abs(literal)]
            for literal in clause
        ):
            raise ValueError("model violates source CNF")


def _file_limit_preexec(maximum_bytes):
    if os.name != "posix":
        return None

    def limit():
        import resource
        resource.setrlimit(resource.RLIMIT_FSIZE, (maximum_bytes, maximum_bytes))

    return limit


def run_bounded(command, seconds, *, maximum_file_bytes=None):
    started = time.monotonic()
    try:
        process = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=seconds,
            check=False,
            preexec_fn=(
                _file_limit_preexec(maximum_file_bytes)
                if maximum_file_bytes is not None else None
            ),
        )
        return process.returncode, process.stdout, time.monotonic() - started, False
    except subprocess.TimeoutExpired as error:
        output = error.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        return 124, output, time.monotonic() - started, True


def deterministic_gzip(source, target, compresslevel=6):
    raw_hash = hashlib.sha256()
    raw_bytes = 0
    with Path(source).open("rb") as input_stream, Path(target).open("wb") as raw_output:
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=raw_output,
            compresslevel=compresslevel, mtime=0,
        ) as output_stream:
            while chunk := input_stream.read(1 << 20):
                raw_hash.update(chunk)
                raw_bytes += len(chunk)
                output_stream.write(chunk)
    return {
        "proof_uncompressed_bytes": raw_bytes,
        "proof_uncompressed_sha256": raw_hash.hexdigest(),
        "proof_compressed_bytes": Path(target).stat().st_size,
        "proof_compressed_sha256": sha256_file(target),
    }


def run_node(spec, base, depth, prefix, output_dir, cadical, checker, lane_bytes):
    lines, header_index, variable_count, clauses = base
    literals = prefix_literals(spec, depth, prefix)
    name = node_name(depth, prefix)
    record = {
        "depth": depth,
        "prefix": prefix,
        "node": name,
        "prefix_literals": list(literals),
    }
    solver_seconds = (
        spec["solver_seconds_leaf"]
        if depth == spec["maximum_depth"]
        else spec["solver_seconds_internal_node"]
    )
    with tempfile.TemporaryDirectory(prefix=name + "-") as temporary_text:
        temporary = Path(temporary_text)
        cnf_path = temporary / "input.cnf"
        proof_path = temporary / "proof.lrat"
        emit_prefix_cnf(
            lines, header_index, variable_count, len(clauses), literals, cnf_path
        )
        code, solver_output, elapsed, timed_out = run_bounded(
            [
                cadical,
                f"--seed={80000001 + prefix + (depth << 12)}",
                "--check", "--checkproof", "--checkprooflrat",
                "--lrat", "--no-binary", str(cnf_path), str(proof_path),
            ],
            solver_seconds,
            maximum_file_bytes=spec["maximum_proof_uncompressed_bytes"],
        )
        record.update({
            "solver_exit": code,
            "solver_seconds": elapsed,
            "solver_output_tail": solver_output[-4000:],
        })
        if timed_out or code in (-25, 153):
            record["state"] = "REFINED_SOLVER_LIMIT"
            return "REFINE", record
        if code == 10:
            try:
                assignment = parse_model(solver_output, variable_count)
                replay_model(clauses, literals, assignment)
            except Exception as error:
                record.update({
                    "state": "TECHNICAL_ERROR",
                    "error": f"model replay: {type(error).__name__}: {error}",
                })
                return "ERROR", record
            record.update({
                "state": "SAT_REPLAYED",
                "true_variables": [
                    variable for variable in range(1, variable_count + 1)
                    if assignment[variable]
                ],
                "all_source_clauses_replayed": True,
            })
            return "SAT", record
        if code != 20 or not proof_path.is_file() or not proof_path.stat().st_size:
            record.update({
                "state": "TECHNICAL_ERROR",
                "error": "solver returned no classified proof outcome",
            })
            return "ERROR", record

        checker_code, checker_output, checker_elapsed, checker_timeout = run_bounded(
            [checker, str(cnf_path), str(proof_path)], spec["checker_seconds"]
        )
        record.update({
            "checker_exit": checker_code,
            "checker_seconds": checker_elapsed,
            "checker_output_tail": checker_output[-4000:],
        })
        if checker_timeout:
            record.update({
                "state": "TECHNICAL_ERROR",
                "error": "independent checker timed out on a completed proof",
            })
            return "ERROR", record
        if checker_code != 0 or "c VERIFIED" not in checker_output:
            record.update({
                "state": "TECHNICAL_ERROR",
                "error": "independent LRAT checker rejected the proof",
            })
            return "ERROR", record

        proof_relative = Path("proofs") / f"{name}.lrat.gz"
        compressed_path = output_dir / proof_relative
        compressed_path.parent.mkdir(parents=True, exist_ok=True)
        proof_metadata = deterministic_gzip(proof_path, compressed_path)
        if (
            proof_metadata["proof_compressed_bytes"]
            > spec["maximum_proof_compressed_bytes"]
            or lane_bytes + proof_metadata["proof_compressed_bytes"]
            > spec["maximum_lane_compressed_bytes"]
        ):
            compressed_path.unlink(missing_ok=True)
            record.update(proof_metadata)
            record["state"] = "REFINED_STORAGE_LIMIT"
            return "REFINE", record
        record.update(proof_metadata)
        record.update({
            "state": "UNSAT_CERTIFIED",
            "proof_file": proof_relative.as_posix(),
            "checker_verified": True,
        })
        return "UNSAT", record


def covered_leaves(spec, records):
    covered = set()
    duplicates = []
    for record in records:
        depth = record["depth"]
        prefix = record["prefix"]
        for suffix in range(1 << (spec["maximum_depth"] - depth)):
            leaf = prefix | (suffix << depth)
            if leaf in covered:
                duplicates.append(leaf)
            covered.add(leaf)
    return covered, sorted(set(duplicates))


def expected_lane_leaves(spec, lane):
    expected = set()
    depth = spec["root_depth"]
    for root in lane_roots(spec, lane):
        for suffix in range(1 << (spec["maximum_depth"] - depth)):
            expected.add(root | (suffix << depth))
    return expected


def lane_payload(spec, lane, attempts, terminals, complete, early_sat, failure):
    return seal({
        "schema": "neutral-adaptive-proof-lane-v1",
        "run_id": spec["run_id"],
        "spec_sha256": spec["_file_sha256"],
        "input_sha256": spec["input_sha256"],
        "lane": lane,
        "assigned_root_prefixes": list(lane_roots(spec, lane)),
        "attempts": attempts,
        "terminal_records": terminals,
        "attempt_count": len(attempts),
        "terminal_count": len(terminals),
        "terminal_state_histogram": dict(sorted(Counter(
            record["state"] for record in terminals
        ).items())),
        "proof_compressed_bytes": sum(
            record.get("proof_compressed_bytes", 0) for record in terminals
        ),
        "complete": complete,
        "early_sat": early_sat,
        "failure": failure,
    })


def public_attempt(record):
    """Keep the checkpoint small without losing exact state/provenance."""
    keys = {
        "depth", "prefix", "node", "prefix_literals", "state",
        "solver_exit", "solver_seconds", "checker_exit", "checker_seconds",
        "proof_uncompressed_bytes", "proof_uncompressed_sha256",
        "proof_compressed_bytes", "proof_compressed_sha256", "proof_file",
        "checker_verified", "error",
    }
    return {key: record[key] for key in keys if key in record}


def verify_attempt_tree(spec, lane, attempts, terminals, complete, early_sat):
    """Replay the deterministic DFS refinement tree, not just its leaf union."""
    by_key = {}
    ordered_keys = []
    for record in attempts:
        key = (record.get("depth"), record.get("prefix"))
        if key in by_key:
            raise ValueError(f"lane {lane} duplicate attempted node")
        if (
            not isinstance(key[0], int)
            or not isinstance(key[1], int)
            or not spec["root_depth"] <= key[0] <= spec["maximum_depth"]
            or not 0 <= key[1] < (1 << key[0])
            or record.get("prefix_literals") != list(prefix_literals(spec, *key))
        ):
            raise ValueError(f"lane {lane} malformed attempted node")
        by_key[key] = record
        ordered_keys.append(key)

    terminal_keys = [(record.get("depth"), record.get("prefix")) for record in terminals]
    if len(terminal_keys) != len(set(terminal_keys)):
        raise ValueError(f"lane {lane} duplicate terminal node")
    if any(key not in by_key for key in terminal_keys):
        raise ValueError(f"lane {lane} terminal was not attempted")

    expected_order = []
    stack = [
        (spec["root_depth"], root)
        for root in reversed(lane_roots(spec, lane))
    ]
    encountered_sat = False
    while stack:
        key = stack.pop()
        expected_order.append(key)
        record = by_key.get(key)
        if record is None:
            raise ValueError(f"lane {lane} missing attempted node {key}")
        state = record.get("state")
        if state in {"UNSAT_CERTIFIED", "SAT_REPLAYED"}:
            if key not in set(terminal_keys):
                raise ValueError(f"lane {lane} terminal state omitted from terminals")
            if state == "SAT_REPLAYED":
                encountered_sat = True
                stack.clear()
        elif state in {"REFINED_SOLVER_LIMIT", "REFINED_STORAGE_LIMIT"}:
            depth, prefix = key
            if depth >= spec["maximum_depth"]:
                raise ValueError(f"lane {lane} refined a maximum-depth node")
            stack.append((depth + 1, prefix | (1 << depth)))
            stack.append((depth + 1, prefix))
        else:
            raise ValueError(f"lane {lane} invalid attempted state {state!r}")
    if ordered_keys != expected_order:
        raise ValueError(f"lane {lane} attempt order/tree mismatch")
    if complete and encountered_sat:
        raise ValueError(f"lane {lane} complete cover contains SAT")
    if early_sat != encountered_sat:
        raise ValueError(f"lane {lane} early-SAT flag mismatch")
    return set(terminal_keys)


def command_contract(args):
    spec = load_spec(args.spec)
    read_dimacs(spec["_input_path"], spec["variable_count"], spec["clause_count"])
    roots = [root for lane in range(spec["lane_count"]) for root in lane_roots(spec, lane)]
    if sorted(roots) != list(range(spec["root_count"])):
        raise ValueError("root partition is not exact")
    print(json.dumps({
        "accepted": True,
        "spec_sha256": spec["_file_sha256"],
        "input_sha256": spec["input_sha256"],
        "root_count": len(roots),
        "leaf_count": spec["leaf_count"],
        "lane_root_histogram": dict(sorted(Counter(
            len(lane_roots(spec, lane)) for lane in range(spec["lane_count"])
        ).items())),
    }, sort_keys=True))


def command_self_test(args):
    spec = load_spec(args.spec)
    all_leaves = set()
    duplicate = set()
    for lane in range(spec["lane_count"]):
        leaves = expected_lane_leaves(spec, lane)
        duplicate.update(all_leaves & leaves)
        all_leaves.update(leaves)
    if duplicate or all_leaves != set(range(spec["leaf_count"])):
        raise ValueError("leaf partition is not exact")
    print(json.dumps({
        "accepted": True,
        "leaf_assignments_replayed": len(all_leaves),
        "overlaps": len(duplicate),
    }, sort_keys=True))


def command_worker(args):
    spec = load_spec(args.spec)
    base = read_dimacs(spec["_input_path"], spec["variable_count"], spec["clause_count"])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    attempts = []
    terminals = []
    stack = [
        (spec["root_depth"], root)
        for root in reversed(lane_roots(spec, args.lane))
    ]
    complete = early_sat = False
    failure = None
    atomic_json(
        args.output_dir / "result.json",
        lane_payload(spec, args.lane, attempts, terminals, False, False, None),
    )
    while stack:
        depth, prefix = stack.pop()
        lane_bytes = sum(record.get("proof_compressed_bytes", 0) for record in terminals)
        outcome, record = run_node(
            spec, base, depth, prefix, args.output_dir,
            args.cadical, args.checker, lane_bytes,
        )
        attempts.append(public_attempt(record))
        if outcome == "UNSAT":
            terminals.append(record)
        elif outcome == "SAT":
            terminals.append(record)
            early_sat = True
            stack.clear()
        elif outcome == "REFINE":
            if depth >= spec["maximum_depth"]:
                failure = f"{record['state']} at maximum depth {depth}, prefix {prefix}"
                stack.clear()
            else:
                stack.append((depth + 1, prefix | (1 << depth)))
                stack.append((depth + 1, prefix))
        else:
            failure = record.get("error", "unclassified technical failure")
            stack.clear()
        if not stack and not early_sat and failure is None:
            covered, duplicates = covered_leaves(spec, terminals)
            complete = not duplicates and covered == expected_lane_leaves(spec, args.lane)
            if not complete:
                failure = "terminal prefixes do not cover the assigned roots exactly"
        atomic_json(
            args.output_dir / "result.json",
            lane_payload(
                spec, args.lane, attempts, terminals,
                complete, early_sat, failure,
            ),
        )
    if failure is not None:
        raise SystemExit(2)


def validate_lane(
    spec, payload, lane, root, allow_partial=False, require_proof_payload=True
):
    check_seal(payload)
    attempts = payload.get("attempts", [])
    terminals = payload.get("terminal_records", [])
    if (
        payload.get("schema") != "neutral-adaptive-proof-lane-v1"
        or payload.get("run_id") != spec["run_id"]
        or payload.get("spec_sha256") != spec["_file_sha256"]
        or payload.get("input_sha256") != spec["input_sha256"]
        or payload.get("lane") != lane
        or payload.get("assigned_root_prefixes") != list(lane_roots(spec, lane))
        or payload.get("attempt_count") != len(attempts)
        or payload.get("terminal_count") != len(terminals)
    ):
        raise ValueError(f"lane {lane} identity mismatch")
    terminal_keys = verify_attempt_tree(
        spec, lane, attempts, terminals,
        payload.get("complete") is True,
        payload.get("early_sat") is True,
    )
    for record in terminals:
        key = (record.get("depth"), record.get("prefix"))
        if key not in terminal_keys:
            raise ValueError(f"lane {lane} terminal-node mismatch")
        if record.get("state") == "UNSAT_CERTIFIED":
            if (
                record.get("solver_exit") != 20
                or record.get("checker_exit") != 0
                or record.get("checker_verified") is not True
            ):
                raise ValueError(f"lane {lane} invalid certified state")
            if require_proof_payload:
                proof = root / record.get("proof_file", "")
                if (
                    not proof.is_file()
                    or proof.stat().st_size != record.get("proof_compressed_bytes")
                    or sha256_file(proof) != record.get("proof_compressed_sha256")
                ):
                    raise ValueError(f"lane {lane} proof payload mismatch")
                raw_hash = hashlib.sha256()
                raw_bytes = 0
                with gzip.open(proof, "rb") as stream:
                    while chunk := stream.read(1 << 20):
                        raw_hash.update(chunk)
                        raw_bytes += len(chunk)
                if (
                    raw_bytes != record.get("proof_uncompressed_bytes")
                    or raw_hash.hexdigest() != record.get("proof_uncompressed_sha256")
                ):
                    raise ValueError(f"lane {lane} proof decompression mismatch")
        elif record.get("state") == "SAT_REPLAYED":
            if (
                record.get("solver_exit") != 10
                or record.get("all_source_clauses_replayed") is not True
                or not isinstance(record.get("true_variables"), list)
            ):
                raise ValueError(f"lane {lane} invalid SAT state")
        else:
            raise ValueError(f"lane {lane} invalid terminal state")
    covered, duplicates = covered_leaves(spec, terminals)
    expected = expected_lane_leaves(spec, lane)
    has_sat = any(record["state"] == "SAT_REPLAYED" for record in terminals)
    if duplicates:
        raise ValueError(f"lane {lane} overlapping terminal prefixes")
    if payload.get("early_sat") is True:
        if not has_sat:
            raise ValueError(f"lane {lane} early-SAT flag without witness")
    elif payload.get("complete") is True:
        if covered != expected or has_sat or payload.get("failure") is not None:
            raise ValueError(f"lane {lane} false completeness claim")
    elif not allow_partial:
        raise ValueError(f"lane {lane} incomplete")
    return terminals


def command_validate_group(args):
    spec = load_spec(args.spec)
    histogram = Counter()
    lanes = []
    for slot in range(spec["logical_workers_per_job"]):
        lane = args.group * spec["logical_workers_per_job"] + slot
        lane_root = args.input_root / f"lane-{lane:03d}"
        payload = json.loads((lane_root / "result.json").read_text(encoding="utf-8"))
        terminals = validate_lane(spec, payload, lane, lane_root, allow_partial=True)
        histogram.update(record["state"] for record in terminals)
        if payload.get("complete") is not True and payload.get("early_sat") is not True:
            raise ValueError(f"lane {lane} is technically incomplete")
        lanes.append(lane)
    atomic_json(args.input_root / "group-summary.json", seal({
        "schema": "neutral-adaptive-proof-group-v1",
        "run_id": spec["run_id"],
        "group": args.group,
        "lanes": lanes,
        "terminal_state_histogram": dict(sorted(histogram.items())),
    }))


def command_collect(args):
    spec = load_spec(args.spec)
    base = read_dimacs(spec["_input_path"], spec["variable_count"], spec["clause_count"])
    payloads = {}
    roots = {}
    for path in args.input_root.rglob("result.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema") != "neutral-adaptive-proof-lane-v1":
            continue
        lane = payload.get("lane")
        if lane in payloads:
            raise ValueError(f"duplicate lane {lane}")
        payloads[lane] = payload
        roots[lane] = path.parent
    missing_lanes = []
    invalid_lanes = []
    all_terminals = []
    complete_lanes = []
    for lane in range(spec["lane_count"]):
        if lane not in payloads:
            missing_lanes.append(lane)
            continue
        try:
            terminals = validate_lane(
                spec, payloads[lane], lane, roots[lane], allow_partial=True,
                require_proof_payload=False,
            )
        except Exception as error:
            invalid_lanes.append({"lane": lane, "error": str(error)})
            continue
        all_terminals.extend({**record, "lane": lane} for record in terminals)
        if payloads[lane].get("complete") is True:
            complete_lanes.append(lane)

    sat_records = [record for record in all_terminals if record["state"] == "SAT_REPLAYED"]
    sat_replay_failures = []
    for record in sat_records:
        truth = record.get("true_variables", [])
        if len(truth) != len(set(truth)):
            sat_replay_failures.append({"node": record["node"], "error": "duplicates"})
            continue
        assignment = {
            variable: variable in set(truth)
            for variable in range(1, spec["variable_count"] + 1)
        }
        try:
            replay_model(base[3], tuple(record["prefix_literals"]), assignment)
        except Exception as error:
            sat_replay_failures.append({"node": record["node"], "error": str(error)})

    unsat_records = [
        record for record in all_terminals if record["state"] == "UNSAT_CERTIFIED"
    ]
    covered, duplicate_leaves = covered_leaves(spec, unsat_records)
    missing_leaves = sorted(set(range(spec["leaf_count"])) - covered)
    full_unsat_cover = (
        not missing_lanes
        and not invalid_lanes
        and len(complete_lanes) == spec["lane_count"]
        and not sat_records
        and not duplicate_leaves
        and not missing_leaves
        and covered == set(range(spec["leaf_count"]))
    )
    if sat_records and not sat_replay_failures:
        conclusion = "SAT_WITNESS_REPLAYED"
        technical_complete = True
    elif full_unsat_cover:
        conclusion = "CERTIFIED_UNSAT_COVER"
        technical_complete = True
    else:
        conclusion = "TECHNICALLY_INCOMPLETE"
        technical_complete = False

    compact_terminals = []
    for record in sorted(all_terminals, key=lambda item: (item["depth"], item["prefix"], item["lane"])):
        compact = dict(record)
        truth = compact.pop("true_variables", None)
        if truth is not None:
            compact["true_variables_sha256"] = hashlib.sha256(
                canonical_bytes(truth)
            ).hexdigest()
            compact["true_variables"] = truth
        compact_terminals.append(compact)
    summary = seal({
        "schema": "neutral-adaptive-proof-collection-v1",
        "run_id": spec["run_id"],
        "workflow_run": args.workflow_run,
        "source_sha": args.source_sha,
        "spec_sha256": spec["_file_sha256"],
        "input_sha256": spec["input_sha256"],
        "root_count": spec["root_count"],
        "leaf_count": spec["leaf_count"],
        "terminal_count": len(all_terminals),
        "terminal_state_histogram": dict(sorted(Counter(
            record["state"] for record in all_terminals
        ).items())),
        "terminal_depth_histogram": dict(sorted(Counter(
            str(record["depth"]) for record in unsat_records
        ).items())),
        "proof_compressed_bytes": sum(
            record.get("proof_compressed_bytes", 0) for record in unsat_records
        ),
        "missing_lanes": missing_lanes,
        "invalid_lanes": invalid_lanes,
        "missing_leaf_count": len(missing_leaves),
        "missing_leaf_ids": missing_leaves[:256],
        "duplicate_leaf_count": len(duplicate_leaves),
        "duplicate_leaf_ids": duplicate_leaves[:256],
        "sat_replay_failures": sat_replay_failures,
        "technical_complete": technical_complete,
        "conclusion": conclusion,
        "proof_contract": (
            "each UNSAT prefix has a CaDiCaL LRAT trace independently accepted "
            "by pinned lrat-check; terminal prefixes must exactly partition all leaves"
        ),
    })
    args.output_dir.mkdir(parents=True, exist_ok=True)
    atomic_json(args.output_dir / "summary.json", summary)
    catalogue = {
        "schema": "neutral-adaptive-proof-catalogue-v1",
        "summary_canonical_sha256": summary["canonical_sha256"],
        "terminal_records": compact_terminals,
    }
    with (args.output_dir / "catalogue.json.gz").open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as stream:
            stream.write(canonical_bytes(catalogue))
    print(json.dumps({
        "technical_complete": technical_complete,
        "conclusion": conclusion,
        "terminal_count": len(all_terminals),
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
    worker.add_argument("--output-dir", type=Path, required=True)
    worker.add_argument("--cadical", default="cadical")
    worker.add_argument("--checker", default="lrat-check")
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
