#!/usr/bin/env python3
"""Collect and independently audit Fourth approach Run 003."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

from deletion_contrasts import canonical_support, verify_sparse_certificate, parse_terms

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
    parser.add_argument("--expected-jobs", type=int, default=4)
    args = parser.parse_args()

    manifests: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
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
        if payload.get("task") != "stage3_deletion_contrasts" or payload.get("complete") is not True:
            errors.append({**manifest, "collector_error": "invalid or incomplete payload"})
            continue
        records.extend(payload.get("records", []))

    child_records = [record for record in records if "child_support" in record]
    independently_reverified = 0
    for record in child_records:
        terms = parse_terms(record["exact_certificate"])
        valid, error = verify_sparse_certificate(record["child_support"], terms)
        if valid and canonical_support(record["child_support"]) == tuple(record["child_canonical_support"]):
            independently_reverified += 1
        else:
            errors.append({"child_class_id": record.get("child_class_id"), "verification_error": error})

    parent_ids = {record["source_canonical_support_id"] for record in child_records}
    parent_classes = {record["parent_minimized_class_id"] for record in child_records}
    child_classes = {record["child_class_id"] for record in child_records}
    target_zero = sum(record.get("classification") == "target_zero" for record in child_records)
    accepted = (
        len(manifests) == args.expected_jobs
        and all(manifest.get("status") == "SUCCESS" for manifest in manifests)
        and not errors
        and len(parent_ids) == 2594
        and len(child_records) == 7782
        and len(parent_classes) == 1
        and len(child_classes) == 1
        and target_zero == len(child_records)
        and independently_reverified == len(child_records)
    )

    run_dir = args.repo / "fourth-approach" / "runs" / f"run-003-{args.run_id}"
    if run_dir.exists():
        raise SystemExit(f"refusing to overwrite {run_dir}")
    run_dir.mkdir(parents=True)
    summary = {
        "schema_version": 1,
        "approach": APPROACH,
        "accepted": accepted,
        "run_id": args.run_id,
        "run_index": 3,
        "task": "stage3_deletion_contrasts",
        "source_sha": args.source_sha,
        "expected_jobs": args.expected_jobs,
        "completed_jobs": sum(manifest.get("status") == "SUCCESS" for manifest in manifests),
        "worker_error_count": len(errors),
        "metrics": {
            "source_minimized_records": len(parent_ids),
            "raw_deletion_children": len(child_records),
            "canonical_minimized_parent_classes": len(parent_classes),
            "canonical_deletion_child_classes": len(child_classes),
            "target_zero_children": target_zero,
            "independently_reverified_children": independently_reverified,
        },
        "scientific_interpretation": (
            "All 2594 Run-002 minima collapse under S6 x S3 to one monochromatic perfect-matching support. "
            "All 7782 one-variable deletions collapse to one two-edge support and are exactly closed by a one-term target_zero certificate."
        ),
        "next_decision": (
            "Do not spend a long run on more deletions of this family. Pivot to supports that contain a monochromatic perfect matching in every color, so target_zero is excluded by construction."
        ),
    }
    write_json(run_dir / "summary.json", summary)
    write_json(run_dir / "job-manifests.json", {"manifests": manifests, "errors": errors})
    write_gzip_json(run_dir / "deletion-contrasts.json.gz", {"records": child_records})
    (run_dir / "README.md").write_text(
        "# Fourth approach Run 003\n\n"
        f"- GitHub Actions run: `{args.run_id}`\n"
        f"- Accepted: `{accepted}`\n"
        "- Run-002 parent records: `2594`\n"
        "- Raw one-variable deletions: `7782`\n"
        "- Canonical minimized parent classes: `1`\n"
        "- Canonical deletion child classes: `1`\n"
        "- Exact target-zero children: `7782`\n\n"
        "This finite exact classification shows that the current certificate library is one trivial target-zero mechanism, not 2594 distinct obstruction mechanisms.\n",
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
        "run_index": 3,
        "task": "stage3_deletion_contrasts",
        "accepted": accepted,
        "metrics": summary["metrics"],
    })
    control.update(
        completed_runs=int(control.get("completed_runs", 3)) + (1 if accepted else 0),
        current_stage=4 if accepted else 3,
        current_stage_name="escape_trivial_target_zero" if accepted else "deletion_contrasts_failed",
        last_run_id=args.run_id,
        last_run_index=3,
        last_run_accepted=accepted,
        next_run_index=4 if accepted else 3,
        next_task="stage4_target_zero_excluded_search" if accepted else "stage3_deletion_contrasts",
        next_spec_path="fourth-approach/run-specs/run-004-stage4-target-zero-excluded-search.json" if accepted else "fourth-approach/run-specs/run-003-stage3-deletion-contrasts.json",
        recommended_next_action="design_long_search_with_all_three_monochromatic_matchings_required" if accepted else "inspect_run_003_failure",
        scientific_stopping_rule="exclude target_zero before spending additional long-run compute",
        tracking_enabled=False,
        run_history=history,
    )
    write_json(control_path, control)
    launch_path = args.repo / "fourth-approach" / "launch.json"
    launch = read_json(launch_path)
    launch.update(
        enabled=False,
        run_index=3,
        task="stage3_deletion_contrasts",
        spec_path="fourth-approach/run-specs/run-003-stage3-deletion-contrasts.json",
        jobs=4,
        minimum_jobs=4,
        runtime_seconds=900,
        max_attempts=0,
        nonce=f"fourth-run-003-completed-{args.run_id}",
    )
    write_json(launch_path, launch)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if accepted else 3


if __name__ == "__main__":
    raise SystemExit(main())
