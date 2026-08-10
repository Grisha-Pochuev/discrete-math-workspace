#!/usr/bin/env python3
"""Strictly accept one fine-shard group and its exact per-shard audits."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys


MASK64 = (1 << 64) - 1
SEEDS = (
    0x243F6A8885A308D3,
    0x13198A2E03707344,
    0xA4093822299F31D0,
    0x082EFA98EC4E6C89,
    0x452821E638D01377,
    0xBE5466CF34E90C6C,
)


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


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def splitmix64(value: int):
    value = (value + 0x9E3779B97F4A7C15) & MASK64
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & MASK64
    return (value ^ (value >> 31)) & MASK64


def partition_group_sizes(shard_count: int):
    if shard_count < 4 or shard_count > 64 or shard_count & (shard_count - 1):
        raise ValueError("shard_count must be a power of two from 4 through 64")
    bits = int(math.log2(shard_count))
    return [
        sum(bool(splitmix64(index ^ SEEDS[bit]) & 1) for index in range(72))
        for bit in range(bits)
    ]


def checked_orbits(record, support, context):
    orbits = record.get("orbits")
    if not isinstance(orbits, list) or len(orbits) != record.get("support_orbits"):
        raise ValueError(f"{context}: support-orbit count mismatch")
    seen = set()
    raw = 0
    for offset, item in enumerate(orbits):
        if not isinstance(item, dict):
            raise ValueError(f"{context}: orbit {offset} is not an object")
        masks = item.get("masks")
        if not isinstance(masks, list) or len(masks) != 8:
            raise ValueError(f"{context}: orbit {offset} has an invalid mask vector")
        if any(not isinstance(mask, int) or not 0 < mask < 512 for mask in masks):
            raise ValueError(f"{context}: orbit {offset} has an out-of-range mask")
        key = tuple(masks)
        if key in seen:
            raise ValueError(f"{context}: duplicate orbit representative")
        seen.add(key)
        sizes = [mask.bit_count() for mask in masks]
        if item.get("edge_sizes") != sizes or sum(sizes) != support:
            raise ValueError(f"{context}: orbit {offset} support replay failed")
        multiplicity = item.get("labelled_multiplicity")
        if not isinstance(multiplicity, int) or multiplicity <= 0:
            raise ValueError(f"{context}: orbit {offset} has invalid multiplicity")
        raw += multiplicity
    if raw != record.get("raw_supports"):
        raise ValueError(f"{context}: labelled multiplicity mismatch")
    return orbits


def enrich_samples(samples, orbits, shard_id):
    result = []
    for sample in samples:
        index = sample.get("support_orbit")
        if not isinstance(index, int) or not 0 <= index < len(orbits):
            raise ValueError("audit sample names an invalid support orbit")
        source = orbits[index]
        result.append({
            **sample,
            "shard_id": shard_id,
            "masks": source["masks"],
            "edge_sizes": source["edge_sizes"],
            "labelled_multiplicity": source["labelled_multiplicity"],
        })
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--case", required=True, type=int)
    parser.add_argument("--support", required=True, type=int)
    parser.add_argument("--group", required=True, type=int)
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--audit-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--survivor-dir", required=True, type=Path)
    parser.add_argument("--pipeline-number", required=True, type=int)
    parser.add_argument("--vcs-revision", required=True)
    parser.add_argument("--vcs-tag", required=True)
    parser.add_argument("--resource-class", required=True)
    args = parser.parse_args()

    errors = []
    records = []
    result = {
        "schema_version": 1,
        "accepted": False,
        "case": args.case,
        "support": args.support,
        "group": args.group,
        "pipeline_number": args.pipeline_number,
        "vcs_revision": args.vcs_revision,
        "vcs_tag": args.vcs_tag,
        "resource_class": args.resource_class,
        "records": records,
        "errors": errors,
    }

    try:
        spec = read(args.spec)
        if spec.get("schema_version") != 1 or spec.get("mode") != "native_exact_fine_layers":
            raise ValueError("unexpected specification schema or mode")
        run_id = spec["run_id"]
        if spec.get("provider") != "circleci" or spec.get("partition") != "parity-log2-v1":
            raise ValueError("unexpected provider or partition")
        shard_count = spec["shard_count"]
        workers_per_job = spec["workers_per_job"]
        groups_per_cell = spec["groups_per_cell"]
        if shard_count != workers_per_job * groups_per_cell:
            raise ValueError("inconsistent shard grouping")
        if spec.get("partition_bits") != int(math.log2(shard_count)):
            raise ValueError("partition bit count mismatch")
        if spec.get("jobs") != len(spec["cells"]) * groups_per_cell:
            raise ValueError("job count mismatch")
        if spec.get("resource_class") != args.resource_class:
            raise ValueError("resource class mismatch")
        if spec.get("trigger_tag") != args.vcs_tag:
            raise ValueError("trigger tag mismatch")
        if not 0 <= args.group < groups_per_cell:
            raise ValueError("group is outside the declared range")
        matches = [
            item for item in spec["cells"]
            if item.get("case") == args.case and item.get("support") == args.support
        ]
        if len(matches) != 1:
            raise ValueError("matrix cell is not uniquely declared")
        cell = matches[0]
        expected_group_sizes = partition_group_sizes(shard_count)
    except Exception as exc:
        errors.append(f"specification: {exc}")
        run_id = None
        shard_count = workers_per_job = 0
        cell = {}
        expected_group_sizes = []

    expected_shards = range(
        args.group * workers_per_job,
        (args.group + 1) * workers_per_job,
    )
    for shard_id in expected_shards:
        context = f"shard {shard_id}"
        source_path = args.input_dir / f"shard-{shard_id}.json"
        exit_path = args.input_dir / f"shard-{shard_id}.exit"
        audit_path = args.audit_dir / f"audit-shard-{shard_id}.json"
        try:
            if not source_path.is_file() or not exit_path.is_file() or not audit_path.is_file():
                raise ValueError("required worker or audit file is missing")
            if exit_path.read_text(encoding="utf-8").strip() != "0":
                raise ValueError("worker exit code is nonzero")
            source = read(source_path)
            expected = {
                "schema_version": 1,
                "run_id": run_id,
                "mode": "exact_support_layer",
                "case": args.case,
                "orbit": cell.get("orbit"),
                "support": args.support,
                "shard_id": shard_id,
                "shard_count": shard_count,
                "partition_version": "parity-log2-v1",
                "symmetry_breaking": True,
                "partition_group_sizes": expected_group_sizes,
                "stabilizer_size": cell.get("stabilizer_size"),
                "term_variables": cell.get("term_variables"),
                "escape_variables": spec.get("expected_escape_variables"),
            }
            for key, value in expected.items():
                if source.get(key) != value:
                    raise ValueError(f"{key}={source.get(key)!r}, expected {value!r}")
            if source.get("status") not in ("OPTIMAL", "INFEASIBLE"):
                raise ValueError("worker status is nonterminal")
            if not source.get("complete_enumeration"):
                raise ValueError("worker enumeration is incomplete")
            if source.get("hit_cap") or source.get("hit_deadline") or source.get("hit_signal"):
                raise ValueError("worker stop flag is set")
            if source.get("enumerated_supports") != source.get("support_orbits"):
                raise ValueError("enumerated support count mismatch")
            orbits = checked_orbits(source, args.support, context)

            audit = read(audit_path)
            audit_expected = {
                "schema_version": 1,
                "run_id": spec.get("audit_run_id"),
                "source_run": args.pipeline_number,
                "source_logical_run": run_id,
                "index": args.case,
                "orbit": cell.get("orbit"),
                "missing_type": cell.get("missing_type"),
                "support": args.support,
                "input_complete": True,
                "audited_support_orbits": source.get("support_orbits"),
            }
            for key, value in audit_expected.items():
                if audit.get(key) != value:
                    raise ValueError(f"audit {key}={audit.get(key)!r}, expected {value!r}")
            histogram = audit.get("two_sided_histogram")
            if not isinstance(histogram, list) or sum(item.get("orbits", -1) for item in histogram) != source["support_orbits"]:
                raise ValueError("audit histogram does not cover the shard")
            if audit.get("all_force_zero") != (audit.get("two_sided_total") == 0):
                raise ValueError("audit force-zero flag is inconsistent")
            if audit.get("all_two_sided_are_coordinate_edge_faces") != (audit.get("nonface_total") == 0):
                raise ValueError("audit nonface flag is inconsistent")
            two_sided_samples = enrich_samples(audit.get("two_sided_samples", []), orbits, shard_id)
            nonface_samples = enrich_samples(audit.get("nonface_samples", []), orbits, shard_id)
            if audit.get("two_sided_total") or audit.get("nonface_total"):
                args.survivor_dir.mkdir(parents=True, exist_ok=True)
                with source_path.open("rb") as source_stream, (
                    args.survivor_dir / f"shard-{shard_id}.json.gz"
                ).open("wb") as compressed_stream:
                    with gzip.GzipFile(
                        filename=f"shard-{shard_id}.json",
                        mode="wb",
                        fileobj=compressed_stream,
                        mtime=0,
                    ) as target_stream:
                        shutil.copyfileobj(source_stream, target_stream)
            records.append({
                "shard_id": shard_id,
                "status": source["status"],
                "complete_enumeration": True,
                "wall_seconds": source.get("wall_seconds"),
                "raw_supports": source["raw_supports"],
                "support_orbits": source["support_orbits"],
                "worker_sha256": digest(source_path),
                "audit_sha256": digest(audit_path),
                "two_sided_total": audit.get("two_sided_total"),
                "two_sided_support_orbits": audit.get("two_sided_support_orbits"),
                "nonface_total": audit.get("nonface_total"),
                "nonface_support_orbits": audit.get("nonface_support_orbits"),
                "two_sided_histogram": histogram,
                "two_sided_samples": two_sided_samples,
                "nonface_samples": nonface_samples,
                "all_force_zero": audit.get("all_force_zero"),
                "all_two_sided_are_coordinate_edge_faces": audit.get(
                    "all_two_sided_are_coordinate_edge_faces"
                ),
            })
        except Exception as exc:
            errors.append(f"{context}: {exc}")

    actual_shards = {item["shard_id"] for item in records}
    if actual_shards != set(expected_shards):
        errors.append("accepted shard coverage is incomplete")
    result.update({
        "run_id": run_id,
        "orbit": cell.get("orbit"),
        "missing_type": cell.get("missing_type"),
        "shard_count": shard_count,
        "partition_version": "parity-log2-v1",
        "expected_shards": list(expected_shards),
        "accepted": not errors,
        "raw_supports": sum(item["raw_supports"] for item in records),
        "audited_support_orbits": sum(item["support_orbits"] for item in records),
        "two_sided_total": sum(item["two_sided_total"] for item in records),
        "two_sided_support_orbits": sum(item["two_sided_support_orbits"] for item in records),
        "nonface_total": sum(item["nonface_total"] for item in records),
        "nonface_support_orbits": sum(item["nonface_support_orbits"] for item in records),
        "all_force_zero": bool(records) and all(item["all_force_zero"] for item in records),
        "all_two_sided_are_coordinate_edge_faces": bool(records) and all(
            item["all_two_sided_are_coordinate_edge_faces"] for item in records
        ),
    })
    atomic_json(args.output, result)
    print(json.dumps({
        key: result[key]
        for key in (
            "run_id", "case", "support", "group", "accepted",
            "audited_support_orbits", "two_sided_total", "nonface_total",
        )
    }, indent=2))
    return 0 if result["accepted"] else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
