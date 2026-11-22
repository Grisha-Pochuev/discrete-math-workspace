#!/usr/bin/env python3
"""Certify a targeted logical cover left open by an earlier proof run."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile

import run080_adaptive_proof as core


def base_leaf_ids(spec):
    parent_depth = spec["parent_prefix_depth"]
    base_depth = spec["base_assignment_depth"]
    leaves = {
        parent | (suffix << parent_depth)
        for parent in spec["parent_prefixes"]
        for suffix in range(1 << (base_depth - parent_depth))
    }
    return tuple(sorted(leaves))


def load_spec(path):
    path = Path(path)
    spec = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema": "neutral-targeted-proof-rescue-v1",
        "run_id": "run-081",
        "physical_jobs": 19,
        "logical_workers_per_job": 4,
        "lane_count": 76,
        "max_parallel": 19,
        "single_threaded_solver_per_worker": True,
        "root_depth": 8,
        "maximum_depth": 16,
        "root_count": 256,
        "leaf_count": 65536,
        "parent_prefix_depth": 7,
        "parent_prefixes": [17, 19, 25, 27, 93, 95, 101, 103],
        "base_assignment_depth": 12,
        "base_partition_variables": [
            127, 128, 129, 130, 131, 132, 133, 134, 135, 1, 2, 3
        ],
        "split_variables": [4, 5, 6, 7, 8, 9, 10, 11],
        "variable_count": 30053,
        "clause_count": 132727,
        "input_sha256":
            "564abcadb9eb164a6a75bef84fddaefc46dbb25076277a693884696b2df55cce",
        "parent_workflow_run": "31750638659",
        "parent_summary_canonical_sha256":
            "543fe868699beed7568b223fce03fb3da6a975d277cdeb1d3bb09df1214f61ac",
        "parent_missing_leaf_count": 256,
        "solver_seconds_internal_node": 30,
        "solver_seconds_leaf": 180,
        "checker_seconds": 300,
        "maximum_proof_uncompressed_bytes": 2147483648,
        "maximum_proof_compressed_bytes": 134217728,
        "maximum_lane_compressed_bytes": 134217728,
        "solver_proof_mode": "external-pinned-lrat-check-only",
    }
    for key, value in required.items():
        if spec.get(key) != value:
            raise ValueError(f"immutable specification mismatch: {key}")

    if len(set(spec["parent_prefixes"])) != len(spec["parent_prefixes"]):
        raise ValueError("duplicate parent prefix")
    if any(
        not isinstance(value, int)
        or not 0 <= value < (1 << spec["parent_prefix_depth"])
        for value in spec["parent_prefixes"]
    ):
        raise ValueError("invalid parent prefix")
    variables = spec["base_partition_variables"] + spec["split_variables"]
    if (
        len(set(variables)) != len(variables)
        or any(
            not isinstance(value, int)
            or not 1 <= value <= spec["variable_count"]
            for value in variables
        )
    ):
        raise ValueError("invalid or repeated partition variable")
    if spec["maximum_depth"] - spec["root_depth"] != len(spec["split_variables"]):
        raise ValueError("logical split depth mismatch")

    leaves = base_leaf_ids(spec)
    if len(leaves) != spec["root_count"]:
        raise ValueError("target root census mismatch")
    input_path = path.parent / spec.get("input_file", "")
    if not input_path.is_file() or core.sha256_file(input_path) != spec["input_sha256"]:
        raise ValueError("input identity mismatch")
    if spec.get("script_sha256") != core.sha256_file(__file__):
        raise ValueError("worker script identity mismatch")
    spec["_base_leaf_ids"] = leaves
    spec["_path"] = str(path.resolve())
    spec["_input_path"] = str(input_path.resolve())
    spec["_file_sha256"] = core.sha256_file(path)
    return spec


def prefix_literals(spec, depth, prefix):
    if not spec["root_depth"] <= depth <= spec["maximum_depth"]:
        raise ValueError("prefix depth outside contract")
    if not 0 <= prefix < (1 << depth):
        raise ValueError("prefix value outside depth")
    root_mask = (1 << spec["root_depth"]) - 1
    root_index = prefix & root_mask
    base_leaf = spec["_base_leaf_ids"][root_index]
    literals = [
        variable if (base_leaf >> bit) & 1 else -variable
        for bit, variable in enumerate(spec["base_partition_variables"])
    ]
    split_count = depth - spec["root_depth"]
    literals.extend(
        variable if (prefix >> (spec["root_depth"] + bit)) & 1 else -variable
        for bit, variable in enumerate(spec["split_variables"][:split_count])
    )
    return tuple(literals)


def run_node(spec, base, depth, prefix, output_dir, cadical, checker, lane_bytes):
    lines, header_index, variable_count, clauses = base
    literals = prefix_literals(spec, depth, prefix)
    name = core.node_name(depth, prefix)
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
        core.emit_prefix_cnf(
            lines, header_index, variable_count, len(clauses), literals, cnf_path
        )
        code, solver_output, elapsed, timed_out = core.run_bounded(
            [
                cadical,
                f"--seed={81000001 + prefix + (depth << 16)}",
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
                assignment = core.parse_model(solver_output, variable_count)
                core.replay_model(clauses, literals, assignment)
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

        checker_code, checker_output, checker_elapsed, checker_timeout = (
            core.run_bounded(
                [checker, str(cnf_path), str(proof_path)],
                spec["checker_seconds"],
            )
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
        proof_metadata = core.deterministic_gzip(proof_path, compressed_path)
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


# Reuse the audited tree, collector and exact-cover machinery while replacing
# only the immutable target mapping and the solver invocation diagnosed above.
core.load_spec = load_spec
core.prefix_literals = prefix_literals
core.run_node = run_node

node_name = core.node_name
lane_roots = core.lane_roots
covered_leaves = core.covered_leaves
expected_lane_leaves = core.expected_lane_leaves
public_attempt = core.public_attempt
lane_payload = core.lane_payload
validate_lane = core.validate_lane


if __name__ == "__main__":
    core.main()
