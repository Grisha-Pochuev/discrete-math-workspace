#!/usr/bin/env python3
"""Strict neutral contract, result writer, and collector for run-084."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil


EXPECTED_CASES = {
    "case-a": {
        "pattern": "111",
        "dimacs_sha256": "5796296705bb4c756d4a8f28d2aad5323e8273b3d5fc5e431d078f6db891c55f",
        "manifest_file_sha256": "1d1efe5e99c781c72d6abc76be51d9e1409674138d18ced8e4e4538d02168ea0",
        "manifest_canonical_sha256": "bcd3688763854b0d87321e5f1b9eddfc9705c4fae9fc443000f90cd97b3bdb29",
        "variable_count": 20745,
        "clause_count": 83698,
    },
    "case-b": {
        "pattern": "21",
        "dimacs_sha256": "ace1efebcb9cb0aea155a57bf06b5243533f1580e89c113fe7b42ceca8afd81d",
        "manifest_file_sha256": "aef0f59f8c6f594cc27fb81d64b19703548d1410aa6ca4b88bcece1de5f522f2",
        "manifest_canonical_sha256": "72a84677df74401684c408d92e5f1e939615aa0bc4dd7edd05e5e26cd19abd00",
        "variable_count": 21297,
        "clause_count": 85355,
    },
}

EXPECTED_SOLVER = {
    "package": "cadical=1.7.4-1",
    "arguments": ["--lrat", "--no-binary"],
    "sat_exit": 10,
    "unsat_exit": 20,
    "seconds": 10800,
}

EXPECTED_CHECKER = {
    "repository": "marijnheule/drat-trim",
    "commit": "2e3b2dc0ecf938addbd779d42877b6ed69d9a985",
    "source": "lrat-check.c",
    "accepted_exit": 0,
    "accepted_line": "c VERIFIED",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(document: dict, field: str = "canonical_outcome_sha256") -> str:
    body = dict(document)
    body.pop(field, None)
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def atomic_json(document: dict, path: Path) -> str:
    body = dict(document)
    body.pop("canonical_outcome_sha256", None)
    digest = canonical_hash(body)
    body["canonical_outcome_sha256"] = digest
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(body, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)
    return digest


def repository_root(spec_path: Path) -> Path:
    resolved = spec_path.resolve()
    if resolved.parent.name != "specs" or resolved.parent.parent.name != "sixth approach":
        raise AssertionError("spec must be under sixth approach/specs")
    return resolved.parent.parent.parent


def load_spec(path: Path) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema") != "run084-pair-proof-spec-v1":
        raise AssertionError("spec schema mismatch")
    if document.get("run_id") != "run-084":
        raise AssertionError("run id mismatch")
    if document.get("formula_schema") != "run084-pair-formula-v1":
        raise AssertionError("formula schema mismatch")
    if document.get("solver") != EXPECTED_SOLVER:
        raise AssertionError("solver contract mismatch")
    if document.get("checker") != EXPECTED_CHECKER:
        raise AssertionError("checker contract mismatch")
    if document.get("preflight_then_automatic_case_jobs") is not True:
        raise AssertionError("automatic preflight fan-out contract missing")
    if document.get("case_job_count") != 2 or document.get("max_parallel") != 2:
        raise AssertionError("case matrix contract mismatch")
    if document.get("outcome_table") != {
        "SAT": "preserve and replay one complete exact model",
        "UNSAT": "preserve LRAT accepted by the pinned independent checker",
        "other": "technical incompleteness; no finite conclusion",
    }:
        raise AssertionError("outcome table mismatch")

    cases = document.get("cases")
    if not isinstance(cases, list) or len(cases) != 2:
        raise AssertionError("case list mismatch")
    mapped = {case.get("case_id"): case for case in cases}
    if set(mapped) != set(EXPECTED_CASES):
        raise AssertionError("case coverage mismatch")
    for case_id, expected in EXPECTED_CASES.items():
        if mapped[case_id] != {"case_id": case_id, **expected}:
            raise AssertionError(("case contract mismatch", case_id))

    root = repository_root(path)
    for path_key, hash_key in (
        ("generator_path", "generator_sha256"),
        ("proof_script_path", "proof_script_sha256"),
    ):
        source = root / document[path_key]
        if not source.is_file() or sha256(source) != document[hash_key]:
            raise AssertionError(("source identity mismatch", path_key))
    return document


def checked_manifest(case_id: str, path: Path) -> dict:
    expected = EXPECTED_CASES[case_id]
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected["manifest_file_sha256"]:
        raise AssertionError("manifest file identity mismatch")
    document = json.loads(raw)
    if canonical_hash(document) != expected["manifest_canonical_sha256"]:
        raise AssertionError("manifest canonical identity mismatch")
    if document.get("canonical_outcome_sha256") != expected["manifest_canonical_sha256"]:
        raise AssertionError("manifest recorded identity mismatch")
    required = {
        "schema": "run084-pair-formula-v1",
        "pattern": expected["pattern"],
        "dimacs_sha256": expected["dimacs_sha256"],
        "variable_count": expected["variable_count"],
        "clause_count": expected["clause_count"],
        "support_size": 20,
        "support_variable_count": 105,
        "direct_collision_clause_count": 3456,
    }
    for key, value in required.items():
        if document.get(key) != value:
            raise AssertionError(("manifest semantic mismatch", key))
    return document


def checked_formula(case_id: str, cnf: Path, manifest: Path) -> dict:
    expected = EXPECTED_CASES[case_id]
    if sha256(cnf) != expected["dimacs_sha256"]:
        raise AssertionError("DIMACS identity mismatch")
    return checked_manifest(case_id, manifest)


def parse_model_text(text: str, variable_count: int) -> dict[int, bool]:
    status = None
    assignment: dict[int, bool] = {}
    for line_number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("c"):
            continue
        if line.startswith("s "):
            if status is not None:
                raise AssertionError("duplicate solver status")
            status = line[2:].strip()
            continue
        if line.startswith("v "):
            for word in line[2:].split():
                literal = int(word)
                if literal == 0:
                    continue
                variable = abs(literal)
                if not 1 <= variable <= variable_count:
                    raise AssertionError(("model variable outside range", line_number))
                value = literal > 0
                if variable in assignment and assignment[variable] != value:
                    raise AssertionError(("conflicting model literal", variable))
                assignment[variable] = value
            continue
        raise AssertionError(("unexpected solver line", line_number, line))
    if status != "SATISFIABLE":
        raise AssertionError("solver output is not SATISFIABLE")
    missing = set(range(1, variable_count + 1)) - set(assignment)
    if missing:
        raise AssertionError(("incomplete model", len(missing), min(missing)))
    return assignment


def solver_status(text: str) -> str:
    states = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("s "):
            states.append(line[2:].strip())
    if len(states) != 1 or states[0] not in ("SATISFIABLE", "UNSATISFIABLE"):
        raise AssertionError(("unclassified solver status", states))
    return states[0]


def replay_dimacs_text(
    text: str,
    assignment: dict[int, bool],
    expected_variables: int,
    expected_clauses: int,
) -> int:
    header = None
    clauses = 0
    for line_number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("c"):
            continue
        if line.startswith("p "):
            words = line.split()
            if header is not None or len(words) != 4 or words[:2] != ["p", "cnf"]:
                raise AssertionError("bad DIMACS header")
            header = tuple(map(int, words[2:]))
            continue
        if header is None:
            raise AssertionError("clause before DIMACS header")
        literals = [int(word) for word in line.split()]
        if not literals or literals[-1] != 0 or any(value == 0 for value in literals[:-1]):
            raise AssertionError(("malformed DIMACS clause", line_number))
        if not all(1 <= abs(value) <= expected_variables for value in literals[:-1]):
            raise AssertionError(("DIMACS variable outside range", line_number))
        if not any(assignment[abs(value)] == (value > 0) for value in literals[:-1]):
            raise AssertionError(("model falsifies clause", clauses + 1))
        clauses += 1
    if header != (expected_variables, expected_clauses) or clauses != expected_clauses:
        raise AssertionError("DIMACS census mismatch")
    return clauses


def canonical_model(assignment: dict[int, bool]) -> str:
    literals = [str(variable if value else -variable) for variable, value in sorted(assignment.items())]
    lines = ["s SATISFIABLE"]
    for start in range(0, len(literals), 20):
        suffix = " 0" if start + 20 >= len(literals) else ""
        lines.append("v " + " ".join(literals[start : start + 20]) + suffix)
    return "\n".join(lines) + "\n"


def deterministic_gzip(source: Path, target: Path) -> None:
    with source.open("rb") as input_stream, target.open("wb") as output_stream:
        with gzip.GzipFile(filename="", mode="wb", fileobj=output_stream, mtime=0) as packed:
            shutil.copyfileobj(input_stream, packed, length=1 << 20)


def gzip_identity(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with gzip.open(path, "rb") as stream:
        while chunk := stream.read(1 << 20):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def file_manifest(root: Path) -> dict:
    result = {}
    for path in sorted(root.iterdir()):
        if path.is_file() and path.name != "result.json":
            result[path.name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    return result


def make_result(args) -> None:
    spec = load_spec(args.spec)
    expected = EXPECTED_CASES[args.case_id]
    manifest_document = checked_formula(args.case_id, args.cnf, args.manifest)
    log_text = args.solver_log.read_text(encoding="ascii", errors="strict")
    status = solver_status(log_text)
    artifact = args.output_dir
    artifact.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(args.manifest, artifact / "manifest.json")
    shutil.copyfile(args.solver_log, artifact / "solver.log")

    record = {
        "schema": "run084-pair-case-result-v1",
        "run_id": spec["run_id"],
        "case_id": args.case_id,
        "pattern": expected["pattern"],
        "source_sha": args.source_sha,
        "github_run_id": str(args.github_run_id),
        "github_run_attempt": int(args.github_run_attempt),
        "dimacs_sha256": expected["dimacs_sha256"],
        "manifest_file_sha256": expected["manifest_file_sha256"],
        "manifest_canonical_sha256": expected["manifest_canonical_sha256"],
        "variable_count": expected["variable_count"],
        "clause_count": expected["clause_count"],
        "solver_package": spec["solver"]["package"],
        "solver_exit": int(args.solver_exit),
        "checker_commit": spec["checker"]["commit"],
    }
    if int(args.solver_exit) == spec["solver"]["sat_exit"] and status == "SATISFIABLE":
        assignment = parse_model_text(log_text, expected["variable_count"])
        checked = replay_dimacs_text(
            args.cnf.read_text(encoding="ascii"),
            assignment,
            expected["variable_count"],
            expected["clause_count"],
        )
        (artifact / "model.txt").write_text(
            canonical_model(assignment), encoding="ascii", newline="\n"
        )
        support_mask = sum(
            1 << (variable - 1)
            for variable in range(1, 106)
            if assignment[variable]
        )
        record.update({
            "outcome": "SAT_MODEL_REPLAYED",
            "complete_model_variable_count": len(assignment),
            "checked_clause_count": checked,
            "support_mask": str(support_mask),
            "support_size": sum(assignment[variable] for variable in range(1, 106)),
        })
    elif int(args.solver_exit) == spec["solver"]["unsat_exit"] and status == "UNSATISFIABLE":
        if args.proof is None or not args.proof.is_file() or args.proof.stat().st_size == 0:
            raise AssertionError("missing LRAT proof")
        if args.checker_log is None or args.checker_exit is None:
            raise AssertionError("missing checker result")
        checker_text = args.checker_log.read_text(encoding="ascii", errors="strict")
        if int(args.checker_exit) != spec["checker"]["accepted_exit"]:
            raise AssertionError("independent checker exit mismatch")
        if spec["checker"]["accepted_line"] not in checker_text.splitlines():
            raise AssertionError("independent checker did not verify proof")
        shutil.copyfile(args.checker_log, artifact / "checker.log")
        deterministic_gzip(args.proof, artifact / "proof.lrat.gz")
        record.update({
            "outcome": "UNSAT_LRAT_VERIFIED",
            "checker_exit": int(args.checker_exit),
            "checker_verified_line": spec["checker"]["accepted_line"],
            "proof_uncompressed_bytes": args.proof.stat().st_size,
            "proof_uncompressed_sha256": sha256(args.proof),
        })
    else:
        raise AssertionError(("solver exit/status disagreement", args.solver_exit, status))

    if manifest_document["pattern"] != record["pattern"]:
        raise AssertionError("result pattern mismatch")
    record["files"] = file_manifest(artifact)
    digest = atomic_json(record, artifact / "result.json")
    print(json.dumps({"case_id": args.case_id, "outcome": record["outcome"], "canonical_outcome_sha256": digest}, sort_keys=True))


def checked_result(spec: dict, result_path: Path) -> dict:
    document = json.loads(result_path.read_text(encoding="utf-8"))
    if document.get("schema") != "run084-pair-case-result-v1":
        raise AssertionError("result schema mismatch")
    case_id = document.get("case_id")
    if case_id not in EXPECTED_CASES:
        raise AssertionError("unknown case id")
    expected = EXPECTED_CASES[case_id]
    required = {
        "run_id": spec["run_id"],
        "pattern": expected["pattern"],
        "dimacs_sha256": expected["dimacs_sha256"],
        "manifest_file_sha256": expected["manifest_file_sha256"],
        "manifest_canonical_sha256": expected["manifest_canonical_sha256"],
        "variable_count": expected["variable_count"],
        "clause_count": expected["clause_count"],
        "solver_package": spec["solver"]["package"],
        "checker_commit": spec["checker"]["commit"],
    }
    for key, value in required.items():
        if document.get(key) != value:
            raise AssertionError(("result identity mismatch", case_id, key))
    if not re.fullmatch(r"[0-9a-f]{40}", str(document.get("source_sha", ""))):
        raise AssertionError("bad source SHA")
    if not str(document.get("github_run_id", "")).isdigit():
        raise AssertionError("bad GitHub run id")
    if canonical_hash(document) != document.get("canonical_outcome_sha256"):
        raise AssertionError("result canonical hash mismatch")

    root = result_path.parent
    files = document.get("files")
    if not isinstance(files, dict):
        raise AssertionError("missing file manifest")
    actual_names = {path.name for path in root.iterdir() if path.is_file() and path.name != "result.json"}
    if set(files) != actual_names:
        raise AssertionError(("artifact file coverage mismatch", case_id))
    for name, metadata in files.items():
        path = root / name
        if metadata != {"bytes": path.stat().st_size, "sha256": sha256(path)}:
            raise AssertionError(("artifact file identity mismatch", case_id, name))
    if files.get("manifest.json", {}).get("sha256") != expected["manifest_file_sha256"]:
        raise AssertionError("artifact manifest identity mismatch")

    outcome = document.get("outcome")
    if outcome == "SAT_MODEL_REPLAYED":
        if document.get("solver_exit") != 10:
            raise AssertionError("SAT exit mismatch")
        if set(files) != {"manifest.json", "model.txt", "solver.log"}:
            raise AssertionError("SAT payload mismatch")
        if document.get("complete_model_variable_count") != expected["variable_count"]:
            raise AssertionError("SAT model completeness mismatch")
        if document.get("checked_clause_count") != expected["clause_count"]:
            raise AssertionError("SAT replay census mismatch")
        if document.get("support_size") != 20:
            raise AssertionError("SAT support size mismatch")
        assignment = parse_model_text(
            (root / "model.txt").read_text(encoding="ascii"),
            expected["variable_count"],
        )
        if solver_status((root / "solver.log").read_text(encoding="ascii")) != "SATISFIABLE":
            raise AssertionError("SAT solver transcript mismatch")
        support_mask = sum(1 << (variable - 1) for variable in range(1, 106) if assignment[variable])
        if str(support_mask) != document.get("support_mask"):
            raise AssertionError("SAT support mask mismatch")
    elif outcome == "UNSAT_LRAT_VERIFIED":
        if document.get("solver_exit") != 20 or document.get("checker_exit") != 0:
            raise AssertionError("UNSAT/checker exit mismatch")
        if document.get("checker_verified_line") != spec["checker"]["accepted_line"]:
            raise AssertionError("UNSAT checker marker mismatch")
        if set(files) != {"checker.log", "manifest.json", "proof.lrat.gz", "solver.log"}:
            raise AssertionError("UNSAT payload mismatch")
        if document.get("proof_uncompressed_bytes", 0) <= 0:
            raise AssertionError("empty proof metadata")
        if solver_status((root / "solver.log").read_text(encoding="ascii")) != "UNSATISFIABLE":
            raise AssertionError("UNSAT solver transcript mismatch")
        checker_lines = (root / "checker.log").read_text(encoding="ascii").splitlines()
        if spec["checker"]["accepted_line"] not in checker_lines:
            raise AssertionError("UNSAT checker transcript mismatch")
        proof_bytes, proof_sha256 = gzip_identity(root / "proof.lrat.gz")
        if (
            proof_bytes != document.get("proof_uncompressed_bytes")
            or proof_sha256 != document.get("proof_uncompressed_sha256")
        ):
            raise AssertionError("UNSAT decompressed proof identity mismatch")
    else:
        raise AssertionError(("unclassified outcome", outcome))
    return document


def collect(args) -> None:
    spec = load_spec(args.spec)
    result_paths = sorted(args.root.rglob("result.json"))
    if len(result_paths) != 2:
        raise AssertionError(("result count mismatch", len(result_paths)))
    records = [checked_result(spec, path) for path in result_paths]
    mapped = {record["case_id"]: record for record in records}
    if len(mapped) != 2 or set(mapped) != set(EXPECTED_CASES):
        raise AssertionError("duplicate or missing case")
    source_shas = {record["source_sha"] for record in records}
    github_runs = {record["github_run_id"] for record in records}
    attempts = {record["github_run_attempt"] for record in records}
    if len(source_shas) != 1 or len(github_runs) != 1 or len(attempts) != 1:
        raise AssertionError("cross-case provenance mismatch")
    summary = {
        "schema": "run084-pair-summary-v1",
        "run_id": spec["run_id"],
        "source_sha": next(iter(source_shas)),
        "github_run_id": next(iter(github_runs)),
        "github_run_attempt": next(iter(attempts)),
        "case_count": 2,
        "outcome_counts": {
            outcome: sum(record["outcome"] == outcome for record in records)
            for outcome in ("SAT_MODEL_REPLAYED", "UNSAT_LRAT_VERIFIED")
        },
        "cases": [
            {
                "case_id": record["case_id"],
                "pattern": record["pattern"],
                "outcome": record["outcome"],
                "case_result_sha256": sha256(result_path),
                "case_canonical_outcome_sha256": record["canonical_outcome_sha256"],
            }
            for record, result_path in sorted(zip(records, result_paths), key=lambda item: item[0]["case_id"])
        ],
        "finite_scope_complete": True,
    }
    digest = atomic_json(summary, args.output)
    print(json.dumps({"case_count": 2, "outcome_counts": summary["outcome_counts"], "canonical_outcome_sha256": digest}, sort_keys=True))


def contract(args) -> None:
    spec = load_spec(args.spec)
    if args.cnf is not None or args.manifest is not None or args.case_id is not None:
        if args.cnf is None or args.manifest is None or args.case_id is None:
            raise AssertionError("case validation needs case, CNF, and manifest")
        checked_formula(args.case_id, args.cnf, args.manifest)
    print(json.dumps({"run_id": spec["run_id"], "case_count": len(spec["cases"]), "contract": "accepted"}, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("contract")
    check.add_argument("--spec", required=True, type=Path)
    check.add_argument("--case-id", choices=tuple(EXPECTED_CASES))
    check.add_argument("--cnf", type=Path)
    check.add_argument("--manifest", type=Path)
    check.set_defaults(function=contract)

    result = subparsers.add_parser("make-result")
    result.add_argument("--spec", required=True, type=Path)
    result.add_argument("--case-id", required=True, choices=tuple(EXPECTED_CASES))
    result.add_argument("--cnf", required=True, type=Path)
    result.add_argument("--manifest", required=True, type=Path)
    result.add_argument("--solver-log", required=True, type=Path)
    result.add_argument("--solver-exit", required=True, type=int)
    result.add_argument("--proof", type=Path)
    result.add_argument("--checker-log", type=Path)
    result.add_argument("--checker-exit", type=int)
    result.add_argument("--source-sha", required=True)
    result.add_argument("--github-run-id", required=True)
    result.add_argument("--github-run-attempt", required=True, type=int)
    result.add_argument("--output-dir", required=True, type=Path)
    result.set_defaults(function=make_result)

    collector = subparsers.add_parser("collect")
    collector.add_argument("--spec", required=True, type=Path)
    collector.add_argument("--root", required=True, type=Path)
    collector.add_argument("--output", required=True, type=Path)
    collector.set_defaults(function=collect)

    args = parser.parse_args()
    args.function(args)


if __name__ == "__main__":
    main()
