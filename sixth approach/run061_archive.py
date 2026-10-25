#!/usr/bin/env python3
"""Build a compact immutable archive for an accepted adaptive shard matrix."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--input-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--workflow-run", required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()

    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    assert summary["run_id"] == spec["run_id"]
    assert summary["accepted"] is True
    assert summary["technical_complete"] is True
    assert summary["validated_shards"] == spec["jobs"]
    assert not summary["failures"]
    if args.output_dir.exists():
        raise ValueError("archive directory already exists")
    args.output_dir.mkdir(parents=True)

    survivors = []
    for item in summary["records"]:
        if not item["scientific_survivor"]:
            continue
        graph = next(
            record for record in spec["graphs"] if record["type"] == item["graph"]
        )
        source = args.input_root / graph["id"] / f'shard-{item["shard"]}.json'
        assert sha256(source) == item["sha256"]
        survivors.append({
            "graph": item["graph"],
            "shard": item["shard"],
            "source_sha256": item["sha256"],
            "record_json": source.read_text(encoding="utf-8"),
        })

    shutil.copyfile(args.spec, args.output_dir / "spec.json")
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
        "archive_format": "adaptive_exact_cut_v1",
        "run_id": spec["run_id"],
        "workflow_run": str(args.workflow_run),
        "source_sha": args.source_sha,
        "validated_shards": summary["validated_shards"],
        "mathematical_closure": summary["mathematical_closure"],
        "scientific_survivors": len(survivors),
        "cut_bundle_sha256": spec["cut_bundle_sha256"],
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    archived = [
        args.output_dir / "manifest.json",
        args.output_dir / "spec.json",
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
