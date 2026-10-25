#!/usr/bin/env python3
"""Build a compact immutable archive from an accepted exact audit matrix."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil


MAX_BLOB_BYTES = 95 * 1024 * 1024
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024


def read_json(path: Path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected an object in {path}")
    return value


def write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_archive(
    spec_path: Path,
    summary_path: Path,
    input_root: Path,
    output_dir: Path,
    workflow_run: int,
    source_sha: str,
) -> None:
    spec = read_json(spec_path)
    summary = read_json(summary_path)
    layers = spec.get("layers")
    if spec.get("mode") != "exact_integer_lattice_audit":
        raise ValueError("unexpected archive mode")
    if not isinstance(layers, list) or not layers:
        raise ValueError("spec must contain layers")
    expected = {(item["index"], item["support"]): item for item in layers}
    if len(expected) != len(layers):
        raise ValueError("duplicate layer in spec")
    if summary.get("accepted") is not True:
        raise ValueError("collector summary is not accepted")
    if summary.get("run_id") != spec.get("run_id"):
        raise ValueError("collector run identity mismatch")
    if summary.get("audited_layers") != len(layers):
        raise ValueError("collector layer count mismatch")
    if not isinstance(workflow_run, int) or workflow_run <= 0:
        raise ValueError("invalid workflow run")
    if len(source_sha) != 40 or any(char not in "0123456789abcdef" for char in source_sha.lower()):
        raise ValueError("invalid source SHA")

    audits = {}
    for path in input_root.rglob("audit.json"):
        item = read_json(path)
        key = (item.get("index"), item.get("support"))
        declared = expected.get(key)
        if declared is None or key in audits:
            raise ValueError(f"unexpected or duplicate audit {key}")
        for field in ("orbit", "missing_type", "source_run", "source_logical_run"):
            if item.get(field) != declared.get(field):
                raise ValueError(f"audit identity mismatch for {key}: {field}")
        if item.get("run_id") != spec["run_id"] or item.get("input_complete") is not True:
            raise ValueError(f"incomplete audit {key}")
        audits[key] = item
    if set(audits) != set(expected):
        raise ValueError("audit coverage mismatch")

    output_dir.mkdir(parents=True, exist_ok=False)
    write_json(output_dir / "spec.json", spec)
    write_json(output_dir / "summary.json", summary)
    write_json(
        output_dir / "provenance.json",
        {
            "schema_version": 1,
            "run_id": spec["run_id"],
            "source_sha": source_sha.lower(),
            "workflow_run": workflow_run,
            "audited_layers": len(audits),
            "archive_format": "compact_exact_audit_v1",
        },
    )
    audit_payload = json.dumps(
        [audits[key] for key in sorted(audits)],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8") + b"\n"
    with (output_dir / "audits.json.gz").open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=9, mtime=0) as stream:
            stream.write(audit_payload)

    archived = [
        output_dir / "audits.json.gz",
        output_dir / "provenance.json",
        output_dir / "spec.json",
        output_dir / "summary.json",
    ]
    sizes = {path.name: path.stat().st_size for path in archived}
    if any(size >= MAX_BLOB_BYTES for size in sizes.values()):
        raise ValueError(f"archive blob exceeds guard: {sizes}")
    if sum(sizes.values()) >= MAX_ARCHIVE_BYTES:
        raise ValueError(f"archive exceeds total guard: {sizes}")
    (output_dir / "checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in archived),
        encoding="utf-8",
    )


def self_test() -> None:
    root = Path.cwd() / "sixth approach" / ".archive-self-test"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir()
    try:
        spec = {
            "schema_version": 1,
            "run_id": "run-test",
            "mode": "exact_integer_lattice_audit",
            "jobs": 1,
            "layers": [{
                "index": 3,
                "orbit": 8,
                "missing_type": "C8",
                "support": 62,
                "source_run": 123,
                "source_logical_run": "run-source",
                "artifact": "source-layer",
            }],
        }
        summary = {
            "schema_version": 1,
            "run_id": "run-test",
            "accepted": True,
            "audited_layers": 1,
        }
        audit = {
            "schema_version": 1,
            "run_id": "run-test",
            "index": 3,
            "orbit": 8,
            "missing_type": "C8",
            "support": 62,
            "source_run": 123,
            "source_logical_run": "run-source",
            "input_complete": True,
            "two_sided_samples": [{"sample": 1}],
        }
        write_json(root / "spec.json", spec)
        write_json(root / "summary.json", summary)
        (root / "input").mkdir()
        write_json(root / "input" / "audit.json", audit)
        build_archive(
            root / "spec.json",
            root / "summary.json",
            root / "input",
            root / "archive",
            456,
            "a" * 40,
        )
        with gzip.open(root / "archive" / "audits.json.gz", "rt", encoding="utf-8") as stream:
            stored = json.load(stream)
        assert stored == [audit]
        assert len((root / "archive" / "checksums.sha256").read_text().splitlines()) == 4
    finally:
        shutil.rmtree(root)
    print("self-test: ok")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--spec", type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--input-root", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--workflow-run", type=int)
    parser.add_argument("--source-sha")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    required = (args.spec, args.summary, args.input_root, args.output_dir, args.workflow_run, args.source_sha)
    if any(value is None for value in required):
        parser.error("archive mode requires all archive arguments")
    build_archive(
        args.spec,
        args.summary,
        args.input_root,
        args.output_dir,
        args.workflow_run,
        args.source_sha,
    )


if __name__ == "__main__":
    main()
