#!/usr/bin/env python3
"""Strictly collect fine-shard group summaries into a compact accepted archive."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys


def read(path: Path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


def digest(path: Path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def resolve_vcs_ref(spec, vcs_tag, vcs_branch):
    trigger = spec.get("trigger")
    if trigger == "tag_push":
        kind, expected, actual = "tag", spec.get("trigger_tag"), vcs_tag
    elif trigger == "api":
        kind, expected, actual = "branch", spec.get("checkout_ref"), vcs_branch
    else:
        raise ValueError(f"unsupported trigger: {trigger!r}")
    if not expected or actual != expected:
        raise ValueError(f"{kind} ref mismatch")
    return kind, actual


def write_json(path: Path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--input-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--pipeline-number", required=True, type=int)
    parser.add_argument("--vcs-revision", required=True)
    ref = parser.add_mutually_exclusive_group(required=True)
    ref.add_argument("--vcs-tag")
    ref.add_argument("--vcs-branch")
    args = parser.parse_args()

    spec = read(args.spec)
    if spec.get("schema_version") != 1 or spec.get("mode") != "native_exact_fine_layers":
        raise ValueError("unexpected specification schema or mode")
    if spec.get("provider") != "circleci":
        raise ValueError("provider mismatch")
    vcs_ref_kind, vcs_ref = resolve_vcs_ref(spec, args.vcs_tag, args.vcs_branch)
    groups = []
    errors = []
    seen_cells = set()
    seen_shards = set()
    for cell in spec["cells"]:
        cell_key = (cell["case"], cell["support"])
        if cell_key in seen_cells:
            raise ValueError("duplicate specification cell")
        seen_cells.add(cell_key)
        for group in range(spec["groups_per_cell"]):
            path = (
                args.input_root
                / spec["run_id"]
                / f"case-{cell['case']}"
                / f"support-{cell['support']}"
                / f"group-{group}"
                / "group-summary.json"
            )
            try:
                record = read(path)
                expected = {
                    "schema_version": 1,
                    "run_id": spec["run_id"],
                    "accepted": True,
                    "case": cell["case"],
                    "orbit": cell["orbit"],
                    "missing_type": cell["missing_type"],
                    "support": cell["support"],
                    "group": group,
                    "pipeline_number": args.pipeline_number,
                    "vcs_revision": args.vcs_revision,
                    "vcs_ref_kind": vcs_ref_kind,
                    "vcs_ref": vcs_ref,
                    "vcs_tag": args.vcs_tag,
                    "vcs_branch": args.vcs_branch,
                    "resource_class": spec["resource_class"],
                    "shard_count": spec["shard_count"],
                    "partition_version": spec["partition"],
                }
                for key, value in expected.items():
                    if record.get(key) != value:
                        raise ValueError(f"{key}={record.get(key)!r}, expected {value!r}")
                if record.get("errors"):
                    raise ValueError("group summary contains errors")
                expected_shards = set(range(
                    group * spec["workers_per_job"],
                    (group + 1) * spec["workers_per_job"],
                ))
                if set(record.get("expected_shards", [])) != expected_shards:
                    raise ValueError("declared group coverage mismatch")
                actual_shards = {item.get("shard_id") for item in record.get("records", [])}
                if actual_shards != expected_shards:
                    raise ValueError("recorded group coverage mismatch")
                for shard in actual_shards:
                    key = (*cell_key, shard)
                    if key in seen_shards:
                        raise ValueError("duplicate cell shard")
                    seen_shards.add(key)
                if sum(item["raw_supports"] for item in record["records"]) != record["raw_supports"]:
                    raise ValueError("group raw-support total mismatch")
                if sum(item["support_orbits"] for item in record["records"]) != record["audited_support_orbits"]:
                    raise ValueError("group audit total mismatch")
                groups.append(record)
            except Exception as exc:
                errors.append(f"case {cell['case']} support {cell['support']} group {group}: {exc}")

    expected_group_count = len(spec["cells"]) * spec["groups_per_cell"]
    expected_shard_count = len(spec["cells"]) * spec["shard_count"]
    if len(groups) != expected_group_count:
        errors.append("group coverage is incomplete")
    if len(seen_shards) != expected_shard_count:
        errors.append("shard coverage is incomplete")
    if errors:
        raise ValueError("; ".join(errors))

    cells = []
    for cell in spec["cells"]:
        selected = [
            item for item in groups
            if item["case"] == cell["case"] and item["support"] == cell["support"]
        ]
        cells.append({
            "case": cell["case"],
            "orbit": cell["orbit"],
            "missing_type": cell["missing_type"],
            "support": cell["support"],
            "groups": len(selected),
            "shards": sum(len(item["records"]) for item in selected),
            "raw_supports": sum(item["raw_supports"] for item in selected),
            "audited_support_orbits": sum(item["audited_support_orbits"] for item in selected),
            "two_sided_total": sum(item["two_sided_total"] for item in selected),
            "two_sided_support_orbits": sum(item["two_sided_support_orbits"] for item in selected),
            "nonface_total": sum(item["nonface_total"] for item in selected),
            "nonface_support_orbits": sum(item["nonface_support_orbits"] for item in selected),
            "all_force_zero": all(item["all_force_zero"] for item in selected),
            "all_two_sided_are_coordinate_edge_faces": all(
                item["all_two_sided_are_coordinate_edge_faces"] for item in selected
            ),
        })

    summary = {
        "schema_version": 1,
        "run_id": spec["run_id"],
        "accepted": True,
        "technical_completion": True,
        "provider": "circleci",
        "pipeline_number": args.pipeline_number,
        "vcs_revision": args.vcs_revision,
        "vcs_ref_kind": vcs_ref_kind,
        "vcs_ref": vcs_ref,
        "vcs_tag": args.vcs_tag,
        "vcs_branch": args.vcs_branch,
        "resource_class": spec["resource_class"],
        "partition_version": spec["partition"],
        "groups": len(groups),
        "shards": len(seen_shards),
        "cells": cells,
        "raw_supports": sum(item["raw_supports"] for item in cells),
        "audited_support_orbits": sum(item["audited_support_orbits"] for item in cells),
        "two_sided_total": sum(item["two_sided_total"] for item in cells),
        "two_sided_support_orbits": sum(item["two_sided_support_orbits"] for item in cells),
        "nonface_total": sum(item["nonface_total"] for item in cells),
        "nonface_support_orbits": sum(item["nonface_support_orbits"] for item in cells),
        "all_force_zero": all(item["all_force_zero"] for item in cells),
        "all_two_sided_are_coordinate_edge_faces": all(
            item["all_two_sided_are_coordinate_edge_faces"] for item in cells
        ),
    }

    args.output_dir.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(args.spec, args.output_dir / "spec.json")
    write_json(args.output_dir / "summary.json", summary)
    provenance = {
        "schema_version": 1,
        "provider": "circleci",
        "pipeline_number": args.pipeline_number,
        "vcs_revision": args.vcs_revision,
        "vcs_ref_kind": vcs_ref_kind,
        "vcs_ref": vcs_ref,
        "vcs_tag": args.vcs_tag,
        "vcs_branch": args.vcs_branch,
        "resource_class": spec["resource_class"],
        "worker_language": spec["worker_language"],
        "audit_engine": spec["audit_engine"],
    }
    write_json(args.output_dir / "provenance.json", provenance)
    with (args.output_dir / "groups.json.gz").open("wb") as compressed_stream:
        with gzip.GzipFile(
            filename="groups.json",
            mode="wb",
            fileobj=compressed_stream,
            mtime=0,
        ) as stream:
            stream.write((json.dumps(groups, sort_keys=True, separators=(",", ":")) + "\n").encode())
    files = sorted(path for path in args.output_dir.iterdir() if path.is_file())
    checksum_lines = [f"{digest(path)}  {path.name}" for path in files]
    (args.output_dir / "checksums.sha256").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    if any(path.stat().st_size >= 95 * 1024 * 1024 for path in args.output_dir.iterdir()):
        raise ValueError("compact archive contains an oversized blob")
    if sum(path.stat().st_size for path in args.output_dir.iterdir()) >= 100 * 1024 * 1024:
        raise ValueError("compact archive exceeds its size limit")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
