#!/usr/bin/env python3
"""Validate a one-cell adaptive rescue specification and emit workflow data."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def canonical_text_sha256(path: Path) -> str:
    payload = path.read_text(encoding="utf-8").replace("\r\n", "\n").encode()
    return hashlib.sha256(payload).hexdigest()


def validate(spec_path: Path, expected_run_id: str, root: Path) -> dict[str, str]:
    specs_root = (root / "sixth approach" / "specs").resolve()
    resolved_spec = spec_path.resolve()
    assert resolved_spec.is_relative_to(specs_root)
    spec = json.loads(resolved_spec.read_text(encoding="utf-8"))

    assert spec["schema_version"] == 1
    assert spec["run_id"] == expected_run_id
    assert spec["mode"] == "adaptive_refined_rescue"
    assert spec["workflow"] == "sixth-approach-adaptive-refine.yml"
    assert spec["runner"] == "ubuntu-24.04"

    parent = spec["parent"]
    base_path = (root / parent["spec_path"]).resolve()
    assert base_path.is_relative_to(specs_root)
    base = json.loads(base_path.read_text(encoding="utf-8"))
    assert canonical_text_sha256(base_path) == parent["spec_sha256"]
    assert base["run_id"] == parent["run_id"]
    assert parent["workflow_run"] > 0
    if "source_sha" in parent:
        assert parent["source_sha"] and len(parent["source_sha"]) == 40
    else:
        assert spec["run_id"] == "run-063", "source_sha is required for new rescues"
    assert parent["shard_count"] == base["shards_per_graph"]
    assert 0 <= parent["shard"] < parent["shard_count"]
    graph = next(item for item in base["graphs"] if item["type"] == parent["graph_type"])
    assert graph["id"] == parent["graph_id"]

    refinement = spec["refinement"]
    assert refinement["partition"] == base["partition"]
    assert refinement["partition_bits"] == base["partition_bits"] + 2
    assert refinement["shard_count"] == parent["shard_count"] * 4
    children = refinement["child_shards"]
    assert children == [
        parent["shard"] + offset * parent["shard_count"] for offset in range(4)
    ]
    assert len(set(children)) == 4
    assert all(child % parent["shard_count"] == parent["shard"] for child in children)

    assert spec["expected_leaf_shards"] == (
        len(base["graphs"]) * base["shards_per_graph"] - 1 + len(children)
    )
    assert spec["compute_jobs"] == 1
    assert spec["workers_per_job"] == 4
    assert spec["workers_per_shard"] == 1
    assert spec["job_timeout_minutes"] <= 150
    assert spec["exact_cut_version"] == base["exact_cut_version"]
    assert spec["cut_bundle_path"] == base["cut_bundle_path"]
    assert spec["cut_bundle_sha256"] == base["cut_bundle_sha256"]
    assert spec["exact_event_cuts"] == graph["exact_event_cuts"]
    assert spec["exact_event_cut_literals"] == graph["exact_event_cut_literals"]

    source_identities = spec.get("source_identities")
    if source_identities is None:
        assert spec["run_id"] == "run-063", "source_identities are required"
        source_identities = [
            {
                "path": "sixth approach/run052_adaptive/exact_event_cuts.h",
                "sha256": spec["cut_header_v1_sha256"],
            },
            {
                "path": "sixth approach/run052_adaptive/exact_event_cuts_v2.h",
                "sha256": spec["cut_header_sha256"],
            },
            {
                "path": "sixth approach/run052_adaptive/main.cpp",
                "sha256": spec["worker_source_sha256"],
            },
        ]
    identities = [
        {"path": parent["spec_path"], "sha256": parent["spec_sha256"]},
        {"path": spec["cut_bundle_path"], "sha256": spec["cut_bundle_sha256"]},
        *source_identities,
    ]
    paths = [item["path"] for item in identities]
    assert len(paths) == len(set(paths))
    for item in identities:
        path = (root / item["path"]).resolve()
        assert path.is_relative_to(root)
        assert canonical_text_sha256(path) == item["sha256"], item["path"]

    return {
        "child_shards": " ".join(map(str, children)),
        "seconds": str(spec["seconds_per_round"]),
        "rounds": str(spec["exchange_rounds"]),
        "worker_seconds": str(spec["worker_seconds"]),
        "memory_mib": str(spec["worker_memory_mib"]),
        "workers": str(spec["workers_per_shard"]),
        "shards": str(refinement["shard_count"]),
        "cut_version": str(spec["exact_cut_version"]),
        "base_spec": parent["spec_path"],
        "parent_workflow_run": str(parent["workflow_run"]),
        "parent_logical_run": parent["run_id"],
        "graph_id": parent["graph_id"],
        "graph_type": parent["graph_type"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    outputs = validate(args.spec, args.run_id, root)
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as stream:
            for key, value in outputs.items():
                stream.write(f"{key}={value}\n")
    print(json.dumps(outputs, sort_keys=True))


if __name__ == "__main__":
    main()
