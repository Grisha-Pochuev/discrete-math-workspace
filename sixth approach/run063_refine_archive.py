#!/usr/bin/env python3
"""Build a compact archive from a parent matrix and refined replacement."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_text_sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_text(encoding="utf-8").replace("\r\n", "\n").encode()
    ).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--base-spec", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--parent-root", required=True, type=Path)
    parser.add_argument("--refinement-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--workflow-run", required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()

    rescue = json.loads(args.spec.read_text(encoding="utf-8"))
    base = json.loads(args.base_spec.read_text(encoding="utf-8"))
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    assert summary["run_id"] == rescue["run_id"]
    assert summary["accepted"] is True and summary["technical_complete"] is True
    assert summary["validated_leaf_shards"] == rescue["expected_leaf_shards"]
    assert summary["parent_workflow_run"] == rescue["parent"]["workflow_run"]
    assert not summary["failures"]
    if args.output_dir.exists():
        raise ValueError("archive directory already exists")
    args.output_dir.mkdir(parents=True)

    graph_ids = {item["type"]: item["id"] for item in base["graphs"]}
    survivors = []
    for item in summary["records"]:
        if not item["scientific_survivor"]:
            continue
        root = (
            args.parent_root if item["source"] == "parent"
            else args.refinement_root
        )
        source = root / graph_ids[item["graph"]] / f'shard-{item["shard"]}.json'
        assert sha256(source) == item["sha256"]
        survivors.append({
            "source": item["source"],
            "graph": item["graph"],
            "shard": item["shard"],
            "source_sha256": item["sha256"],
            "record_json": source.read_text(encoding="utf-8"),
        })

    shutil.copyfile(args.spec, args.output_dir / "spec.json")
    shutil.copyfile(args.base_spec, args.output_dir / "base-spec.json")
    shutil.copyfile(args.summary, args.output_dir / "summary.json")
    payload = json.dumps(
        {"schema_version": 1, "survivors": survivors},
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    with (args.output_dir / "survivors.json.gz").open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as stream:
            stream.write(payload)

    manifest = {
        "schema_version": 1,
        "archive_format": "adaptive_refined_rescue_v1",
        "run_id": rescue["run_id"],
        "workflow_run": str(args.workflow_run),
        "source_sha": args.source_sha,
        "parent_run_id": rescue["parent"]["run_id"],
        "parent_workflow_run": rescue["parent"]["workflow_run"],
        "validated_leaf_shards": summary["validated_leaf_shards"],
        "mathematical_closure": summary["mathematical_closure"],
        "scientific_survivors": len(survivors),
        "base_spec_sha256": canonical_text_sha256(args.base_spec),
        "cut_bundle_sha256": rescue["cut_bundle_sha256"],
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    archived = [
        args.output_dir / "manifest.json",
        args.output_dir / "spec.json",
        args.output_dir / "base-spec.json",
        args.output_dir / "summary.json",
        args.output_dir / "survivors.json.gz",
    ]
    sizes = {path.name: path.stat().st_size for path in archived}
    if any(size > 5 * 1024 * 1024 for size in sizes.values()):
        raise ValueError(f"archive blob exceeds guard: {sizes}")
    if sum(sizes.values()) > 10 * 1024 * 1024:
        raise ValueError(f"archive exceeds total guard: {sizes}")
    (args.output_dir / "checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in archived),
        encoding="utf-8",
    )
    print(json.dumps({
        "archive": str(args.output_dir),
        "bytes": sum(sizes.values()),
        "scientific_survivors": len(survivors),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
