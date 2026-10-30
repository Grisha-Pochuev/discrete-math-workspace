#!/usr/bin/env python3
"""Collect Fourth approach Run 004 fixed-support certificate minimization."""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

from fixed_support_minimize import parse_exact_terms, verify_sparse_certificate

APPROACH = "fourth-approach-obstruction-guided-exact-synthesis"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_gzip_json(path: Path) -> Any:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def write_gzip_json(path: Path, payload: Any) -> None:
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as handle:
        json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--expected-jobs", type=int, default=20)
    parser.add_argument("--minimum-jobs", type=int, default=18)
    args = parser.parse_args()

    manifests: list[dict[str, Any]] = []
    records_by_id: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []
    complete_shards = 0
    for directory in sorted({path.parent for path in args.artifacts.rglob("manifest.json")}):
        manifest = read_json(directory / "manifest.json")
        manifests.append(manifest)
        if manifest.get("status") != "SUCCESS":
            errors.append(manifest)
            continue
        result_path = directory / str(manifest.get("result_file", ""))
        if not result_path.is_file():
            errors.append({**manifest, "collector_error": "missing result file"})
            continue
        payload = read_gzip_json(result_path)
        if payload.get("task") != "stage4_fixed_support_certificate_minimization":
            errors.append({**manifest, "collector_error": "wrong payload task"})
            continue
        if payload.get("complete") is True:
            complete_shards += 1
        else:
            errors.append({**manifest, "collector_error": "incomplete shard"})
        for record in payload.get("records", []):
            class_id = str(record.get("canonical_support_id", ""))
            if not class_id:
                errors.append({"collector_error": "record without class id"})
                continue
            if class_id in records_by_id and records_by_id[class_id] != record:
                errors.append({"collector_error": "conflicting record", "canonical_support_id": class_id})
            else:
                records_by_id[class_id] = record

    records = [records_by_id[key] for key in sorted(records_by_id)]
    independently_reverified = 0
    support_changed = 0
    missing_mono = 0
    for record in records:
        terms = parse_exact_terms({
            "column_descriptors": [[term["row"], term["feature"]] for term in record["minimized_terms"]],
            "exact_rational_coefficients": [[term["real"], term["imag"]] for term in record["minimized_terms"]],
        })
        valid, error = verify_sparse_certificate(record["fixed_support_variables"], terms)
        if valid:
            independently_reverified += 1
        else:
            errors.append({"canonical_support_id": record["canonical_support_id"], "verification_error": error})
        if record.get("support_unchanged") is not True:
            support_changed += 1
        if not all(int(value) > 0 for value in record.get("mono_matching_counts", [])):
            missing_mono += 1

    completed_jobs = sum(manifest.get("status") == "SUCCESS" for manifest in manifests)
    accepted = (
        completed_jobs >= args.minimum_jobs
        and len(manifests) <= args.expected_jobs
        and complete_shards == args.expected_jobs
        and not errors
        and len(records) == 2594
        and independently_reverified == len(records)
        and support_changed == 0
        and missing_mono == 0
    )
    term_distribution = Counter(int(record["minimized_nonzero_terms"]) for record in records)
    original_terms = sum(int(record["original_nonzero_terms"]) for record in records)
    minimized_terms = sum(int(record["minimized_nonzero_terms"]) for record in records)
    terms_removed = original_terms - minimized_terms
    metrics = {
        "source_support_classes": len(records),
        "completed_jobs": completed_jobs,
        "complete_shards": complete_shards,
        "independently_reverified": independently_reverified,
        "supports_changed": support_changed,
        "supports_missing_monochromatic_target": missing_mono,
        "certificates_improved": sum(int(record["terms_removed"]) > 0 for record in records),
        "original_nonzero_terms": original_terms,
        "minimized_nonzero_terms": minimized_terms,
        "certificate_terms_removed": terms_removed,
        "term_count_distribution": {str(key): value for key, value in sorted(term_distribution.items())},
        "total_optimization_attempts": sum(int(record.get("optimization_attempts", 0)) for record in records),
    }
    summary = {
        "schema_version": 1,
        "approach": APPROACH,
        "accepted": accepted,
        "run_id": args.run_id,
        "run_index": 4,
        "task": "stage4_fixed_support_certificate_minimization",
        "source_sha": args.source_sha,
        "expected_jobs": args.expected_jobs,
        "minimum_jobs": args.minimum_jobs,
        "completed_jobs": completed_jobs,
        "worker_error_count": len(errors),
        "metrics": metrics,
        "scientific_interpretation": (
            "Every certificate is minimized on its unchanged original support, with all three monochromatic target matchings still present. "
            "These compact exact identities therefore describe the same support-restricted systems rather than unrelated target-zero sub-supports."
        ),
        "next_decision": (
            "Canonicalize the fixed-support certificate mechanisms and bridge them to the strongest old-basin and independent Second approach candidates."
        ),
    }

    run_dir = args.repo / "fourth-approach" / "runs" / f"run-004-{args.run_id}"
    if run_dir.exists():
        raise SystemExit(f"refusing to overwrite {run_dir}")
    run_dir.mkdir(parents=True)
    write_json(run_dir / "summary.json", summary)
    write_json(run_dir / "job-manifests.json", {"manifests": manifests, "errors": errors})
    write_gzip_json(run_dir / "fixed-support-certificates.json.gz", {"records": records})
    (run_dir / "README.md").write_text(
        "# Fourth approach Run 004\n\n"
        f"- GitHub Actions run: `{args.run_id}`\n"
        f"- Accepted: `{accepted}`\n"
        f"- Fixed original support classes: `{len(records)}`\n"
        f"- Independently reverified: `{independently_reverified}`\n"
        f"- Certificate terms removed: `{terms_removed}`\n"
        f"- Supports changed: `{support_changed}`\n"
        f"- Supports missing a monochromatic target: `{missing_mono}`\n\n"
        "Unlike Run 002, this run never deletes support variables. Each minimized identity remains a certificate for the original recorded support-restricted system.\n",
        encoding="utf-8",
    )
    checksum_lines = []
    for path in sorted(run_dir.iterdir()):
        if path.is_file() and path.name != "checksums.sha256":
            checksum_lines.append(f"{sha256(path)}  {path.name}")
    (run_dir / "checksums.sha256").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    control_path = args.repo / "fourth-approach" / "control.json"
    control = read_json(control_path)
    history = list(control.get("run_history", []))
    history.append({
        "run_id": args.run_id,
        "run_index": 4,
        "task": summary["task"],
        "accepted": accepted,
        "metrics": metrics,
    })
    control.update(
        completed_runs=int(control.get("completed_runs", 4)) + (1 if accepted else 0),
        current_stage=5 if accepted else 4,
        current_stage_name="bridge_fixed_support_certificates_to_second_approach" if accepted else "fixed_support_minimization_failed",
        last_run_id=args.run_id,
        last_run_index=4,
        last_run_accepted=accepted,
        next_run_index=5 if accepted else 4,
        next_task="stage5_bridge_second_approach" if accepted else summary["task"],
        next_spec_path="fourth-approach/run-specs/run-005-stage5-bridge-second-approach.json" if accepted else "fourth-approach/run-specs/run-004-stage4-fixed-support-minimization.json",
        recommended_next_action="design_bridge_to_old_and_independent_second_approach_pools" if accepted else "inspect_run_004_failure",
        scientific_stopping_rule="do not infer the full conjecture from support-restricted n=6 certificates",
        tracking_enabled=False,
        run_history=history,
    )
    write_json(control_path, control)
    launch_path = args.repo / "fourth-approach" / "launch.json"
    launch = read_json(launch_path)
    launch.update(
        enabled=False,
        run_index=4,
        task=summary["task"],
        spec_path="fourth-approach/run-specs/run-004-stage4-fixed-support-minimization.json",
        jobs=20,
        minimum_jobs=18,
        runtime_seconds=20700,
        max_attempts=0,
        nonce=f"fourth-run-004-completed-{args.run_id}",
    )
    write_json(launch_path, launch)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if accepted else 3


if __name__ == "__main__":
    raise SystemExit(main())
