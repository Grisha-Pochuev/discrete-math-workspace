#!/usr/bin/env python3
"""Collect and replay all branches of the neutral run-069 support search."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_dimacs(path: Path):
    variables = clauses_expected = None
    clauses = []
    for raw in path.read_text(encoding="ascii").splitlines():
        line = raw.strip()
        if not line or line.startswith("c"):
            continue
        if line.startswith("p "):
            _, kind, variable_text, clause_text = line.split()
            if kind != "cnf" or variables is not None:
                raise ValueError("invalid DIMACS header")
            variables = int(variable_text)
            clauses_expected = int(clause_text)
            continue
        values = [int(value) for value in line.split()]
        if not values or values[-1] != 0:
            raise ValueError("invalid DIMACS clause")
        clauses.append(tuple(values[:-1]))
    if variables is None or clauses_expected != len(clauses):
        raise ValueError("DIMACS count mismatch")
    return variables, clauses


def literal_true(literal, assignment):
    return assignment[literal - 1] if literal > 0 else not assignment[-literal - 1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--dimacs", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--branches", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workflow-run", required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    branch_spec = json.loads(args.branches.read_text(encoding="utf-8"))
    if sha256(args.dimacs) != manifest["dimacs_sha256"]:
        raise ValueError("DIMACS hash mismatch")
    if branch_spec["base_dimacs_sha256"] != manifest["dimacs_sha256"]:
        raise ValueError("branch/DIMACS identity mismatch")
    expected = {job["id"]: job for job in branch_spec["jobs"]}
    if len(expected) != 20:
        raise ValueError("unexpected branch coverage")
    result_paths = sorted(args.input_root.rglob("result.json"))
    results = []
    seen = set()
    for path in result_paths:
        result = json.loads(path.read_text(encoding="utf-8"))
        job_id = result["job"]["id"]
        if job_id not in expected or job_id in seen:
            raise ValueError(f"unexpected or duplicate result {job_id}")
        seen.add(job_id)
        if result["job"] != expected[job_id]:
            raise ValueError(f"job identity mismatch for {job_id}")
        if result["dimacs_sha256"] != manifest["dimacs_sha256"]:
            raise ValueError(f"DIMACS provenance mismatch for {job_id}")
        if result["manifest_sha256"] != sha256(args.manifest):
            raise ValueError(f"manifest provenance mismatch for {job_id}")
        if result["branches_sha256"] != sha256(args.branches):
            raise ValueError(f"branch provenance mismatch for {job_id}")
        results.append(result)
    missing = sorted(set(expected) - seen)
    if missing:
        raise ValueError(f"missing branch results: {missing}")

    variable_count, clauses = parse_dimacs(args.dimacs)
    survivors = []
    for result in results:
        if result["status"] not in {"OPTIMAL", "FEASIBLE"}:
            continue
        true_literals = set(result["assignment_true_literals"])
        assignment = [index + 1 in true_literals for index in range(variable_count)]
        if any(not any(literal_true(literal, assignment) for literal in clause) for clause in clauses):
            raise ValueError(f"assignment replay failed for {result['job']['id']}")
        if any(
            not literal_true(literal, assignment)
            for literal in result["job"]["assumption_literals"]
        ):
            raise ValueError(f"assumption replay failed for {result['job']['id']}")
        selected = [index for index in range(108) if assignment[index]]
        if selected != result["selected_arms"] or result["cross_colour_selected"] != 21:
            raise ValueError(f"active-arm replay failed for {result['job']['id']}")
        survivors.append(
            {
                "job_id": result["job"]["id"],
                "orbit": result["job"]["orbit"],
                "selected_arms": selected,
                "selected_arms_sha256": result["selected_arms_sha256"],
            }
        )

    results.sort(key=lambda item: item["job"]["id"])
    histogram = Counter(result["status"] for result in results)
    if survivors:
        scientific_status = "boolean_support_survivor_found"
    elif histogram.get("UNKNOWN", 0):
        scientific_status = "bounded_search_incomplete"
    elif set(histogram) <= {"INFEASIBLE"}:
        scientific_status = "no_survivor_found_without_portable_refutation"
    else:
        scientific_status = "unexpected_solver_state"

    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "schema": "run-069-support-collection-v1",
        "evidence_level": "exact survivor replay; negative statuses remain diagnostic",
        "workflow_run": str(args.workflow_run),
        "source_sha": args.source_sha,
        "dimacs_sha256": manifest["dimacs_sha256"],
        "manifest_sha256": sha256(args.manifest),
        "branches_sha256": sha256(args.branches),
        "expected_jobs": 20,
        "received_jobs": len(results),
        "status_histogram": dict(sorted(histogram.items())),
        "scientific_status": scientific_status,
        "survivor_count": len(survivors),
        "survivors": survivors,
        "scope_warning": (
            "A Boolean support survivor still requires the exact multiplicative-character "
            "audit and solution of the complex six-term equations.  INFEASIBLE without "
            "a portable proof is not a no-go theorem."
        ),
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    payload = (json.dumps(results, sort_keys=True, separators=(",", ":")) + "\n").encode()
    with (args.output_dir / "results.json.gz").open("wb") as raw_stream:
        with gzip.GzipFile(fileobj=raw_stream, mode="wb", mtime=0) as stream:
            stream.write(payload)
    shutil.copyfile(args.manifest, args.output_dir / "input-manifest.json")
    shutil.copyfile(args.branches, args.output_dir / "branch-partition.json")
    files = [
        args.output_dir / "summary.json",
        args.output_dir / "results.json.gz",
        args.output_dir / "input-manifest.json",
        args.output_dir / "branch-partition.json",
    ]
    (args.output_dir / "checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in files), encoding="ascii"
    )
    print(json.dumps({"scientific_status": scientific_status, "survivors": len(survivors), "statuses": dict(histogram)}, sort_keys=True))


if __name__ == "__main__":
    main()
