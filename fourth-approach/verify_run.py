#!/usr/bin/env python3
"""Independent structural verifier for Fourth approach run archives."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from schema import APPROACH, read_json


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_gzip_json(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def verify_checksums(run_dir: Path) -> None:
    expected = {}
    for line in (run_dir / "checksums.sha256").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        expected[name] = digest
    for name, digest in expected.items():
        path = run_dir / name
        if not path.is_file():
            raise SystemExit(f"checksum file is missing: {name}")
        if sha256(path) != digest:
            raise SystemExit(f"checksum mismatch: {name}")


def verify_stage0(run_dir: Path, summary: dict) -> None:
    required = ["source-manifest.json", "job-manifests.json"]
    for name in required:
        if not (run_dir / name).is_file():
            raise SystemExit(f"missing stage0 archive file: {name}")
    manifest = read_json(run_dir / "source-manifest.json")
    jobs = read_json(run_dir / "job-manifests.json")
    if manifest.get("approach") != APPROACH:
        raise SystemExit("approach mismatch")
    if int(summary.get("completed_jobs", -1)) != sum(
        1 for item in jobs.get("manifests", []) if item.get("status") == "SUCCESS"
    ):
        raise SystemExit("completed job count mismatch")
    paths = [record.get("path") for record in manifest.get("records", [])]
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise SystemExit("source manifest paths are not sorted and unique")


def verify_stage1(run_dir: Path, summary: dict) -> None:
    required = ["canonical-classes.json", "verification-results.json.gz", "job-manifests.json"]
    for name in required:
        if not (run_dir / name).is_file():
            raise SystemExit(f"missing stage1 archive file: {name}")
    classes_document = read_json(run_dir / "canonical-classes.json")
    results = read_gzip_json(run_dir / "verification-results.json.gz")
    jobs = read_json(run_dir / "job-manifests.json")
    records = list(results.get("records", []))
    keys = [str(record.get("candidate_key", "")) for record in records]
    if not all(keys) or keys != sorted(keys) or len(keys) != len(set(keys)):
        raise SystemExit("verification candidate keys are not sorted and unique")
    verified = [record for record in records if record.get("independent_exact_verified") is True]
    rejected = [
        record for record in records
        if record.get("production_exact_verified") is True
        and record.get("independent_exact_verified") is not True
    ]
    if rejected:
        raise SystemExit("archive contains rejected production exact claims")
    classes = list(classes_document.get("classes", []))
    support_ids = [str(entry.get("canonical_support_id", "")) for entry in classes]
    if not all(support_ids) or support_ids != sorted(support_ids) or len(support_ids) != len(set(support_ids)):
        raise SystemExit("canonical support classes are not sorted and unique")
    metrics = summary.get("metrics", {})
    if int(metrics.get("independently_verified_certificates", -1)) != len(verified):
        raise SystemExit("independently verified count mismatch")
    if int(metrics.get("canonical_support_classes", -1)) != len(classes):
        raise SystemExit("canonical class count mismatch")
    actual_signatures = {
        str(record.get("canonical_certificate_signature"))
        for record in verified
        if record.get("canonical_certificate_signature")
    }
    if int(metrics.get("canonical_certificate_signatures", -1)) != len(actual_signatures):
        raise SystemExit("canonical certificate signature count mismatch")
    completed = sum(
        1 for item in jobs.get("manifests", [])
        if item.get("status") in {"SUCCESS", "BOUNDED_INCOMPLETE"}
    )
    if int(summary.get("completed_jobs", -1)) != completed:
        raise SystemExit("completed stage1 job count mismatch")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument("--require-accepted", action="store_true")
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    for name in ("README.md", "summary.json", "checksums.sha256"):
        if not (run_dir / name).is_file():
            raise SystemExit(f"missing archive file: {name}")
    summary = read_json(run_dir / "summary.json")
    if summary.get("approach") != APPROACH:
        raise SystemExit("approach mismatch")
    if args.require_accepted and summary.get("accepted") is not True:
        raise SystemExit("run is not accepted")
    task = summary.get("task")
    if task == "stage0_source_inventory":
        verify_stage0(run_dir, summary)
    elif task == "stage1_canonicalize_verify":
        verify_stage1(run_dir, summary)
    else:
        raise SystemExit(f"unsupported archive task: {task}")
    verify_checksums(run_dir)
    print(json.dumps({"verified": True, "run_dir": str(run_dir), "summary": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
