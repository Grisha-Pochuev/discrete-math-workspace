#!/usr/bin/env python3
"""Adversarial contract tests for the neutral run-084 pair package."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile

import run084_pair_proof as proof


def must_fail(action) -> None:
    try:
        action()
    except (AssertionError, KeyError, ValueError):
        return
    raise AssertionError("invalid fixture was accepted")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True, type=Path)
    args = parser.parse_args()

    document = proof.load_spec(args.spec)
    if len(document["cases"]) != 2:
        raise AssertionError("frozen case count mismatch")

    assignment = proof.parse_model_text(
        "c neutral fixture\ns SATISFIABLE\nv 1 -2 3 0\n", 3
    )
    if assignment != {1: True, 2: False, 3: True}:
        raise AssertionError("valid model parse mismatch")
    cnf = "p cnf 3 3\n1 2 0\n-2 3 0\n1 -3 0\n"
    if proof.replay_dimacs_text(cnf, assignment, 3, 3) != 3:
        raise AssertionError("valid model replay mismatch")
    canonical = proof.canonical_model(assignment)
    if proof.parse_model_text(canonical, 3) != assignment:
        raise AssertionError("canonical model round-trip mismatch")

    must_fail(lambda: proof.parse_model_text("s UNSATISFIABLE\nv 1 -2 3 0\n", 3))
    must_fail(lambda: proof.parse_model_text("s SATISFIABLE\nv 1 -2 0\n", 3))
    must_fail(lambda: proof.parse_model_text("s SATISFIABLE\nv 1 -1 2 3 0\n", 3))
    must_fail(lambda: proof.solver_status("s SATISFIABLE\ns UNSATISFIABLE\n"))
    must_fail(lambda: proof.replay_dimacs_text("p cnf 3 1\n-1 2 0\n", assignment, 3, 1))
    must_fail(lambda: proof.replay_dimacs_text("p cnf 3 2\n1 0\n", assignment, 3, 2))

    root = proof.repository_root(args.spec)
    generated = root / "generated"
    for case_id in proof.EXPECTED_CASES:
        proof.checked_formula(
            case_id,
            generated / f"{case_id}.cnf",
            generated / f"{case_id}.json",
        )

    # The bundled Windows runtime in the desktop sandbox cannot reopen a
    # TemporaryDirectory below a non-ASCII workspace path.  Linux preflight
    # must still exercise the complete filesystem plumbing below.
    if os.name == "nt":
        print("run084-pair-proof-tests: ok (Linux filesystem test deferred)")
        return

    # Exercise the complete artifact/collector plumbing with a synthetic
    # checker transcript.  This tests transport only; the workflow preflight
    # separately runs the real pinned checker on a genuine LRAT proof.
    with tempfile.TemporaryDirectory(prefix="run084-contract-", dir=root) as text:
        temporary = Path(text)
        bundles = temporary / "bundles"
        for case_id in proof.EXPECTED_CASES:
            work = temporary / case_id
            work.mkdir()
            solver_log = work / "solver.log"
            solver_log.write_text("s UNSATISFIABLE\n", encoding="ascii")
            candidate = work / "proof.lrat"
            candidate.write_text("1 0 0\n", encoding="ascii")
            checker = work / "checker.log"
            checker.write_text("c VERIFIED\n", encoding="ascii")
            proof.make_result(SimpleNamespace(
                spec=args.spec,
                case_id=case_id,
                cnf=generated / f"{case_id}.cnf",
                manifest=generated / f"{case_id}.json",
                solver_log=solver_log,
                solver_exit=20,
                proof=candidate,
                checker_log=checker,
                checker_exit=0,
                source_sha="0" * 40,
                github_run_id="1",
                github_run_attempt=1,
                output_dir=bundles / case_id,
            ))
        summary_path = temporary / "summary.json"
        proof.collect(SimpleNamespace(spec=args.spec, root=bundles, output=summary_path))
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary["outcome_counts"] != {
            "SAT_MODEL_REPLAYED": 0,
            "UNSAT_LRAT_VERIFIED": 2,
        }:
            raise AssertionError("synthetic collector split mismatch")
        first = bundles / "case-a" / "checker.log"
        first.write_text("c CORRUPTED\n", encoding="ascii")
        must_fail(lambda: proof.checked_result(document, bundles / "case-a" / "result.json"))

    print("run084-pair-proof-tests: ok")


if __name__ == "__main__":
    main()
