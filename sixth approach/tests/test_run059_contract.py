#!/usr/bin/env python3
"""Synthetic end-to-end test of the fine-shard acceptance contract."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys


TRACK = Path(__file__).resolve().parents[1]
SPEC_PATH = (
    Path(sys.argv[1]).resolve()
    if len(sys.argv) > 1
    else TRACK / "specs" / "run-059-fine-rescue.json"
)
GROUP_SCRIPT = TRACK / "run059_group_audit.py"
COLLECT_SCRIPT = TRACK / "run059_collect.py"
PIPELINE = 17
REVISION = "0" * 40
TEST_ROOT = TRACK / "tests" / "contract-tmp"


def load_group_module():
    spec = importlib.util.spec_from_file_location("run059_group_audit", GROUP_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main():
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    if spec.get("trigger") == "tag_push":
        ref_argument, ref_value = "--vcs-tag", spec["trigger_tag"]
    elif spec.get("trigger") == "api":
        ref_argument, ref_value = "--vcs-branch", spec["checkout_ref"]
    else:
        raise ValueError("unsupported synthetic trigger")
    group_module = load_group_module()
    group_sizes = group_module.partition_group_sizes(spec["shard_count"])
    for path in TEST_ROOT.iterdir():
        if path.name == ".gitignore":
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    try:
        root = TEST_ROOT
        workspace = root / "workspace"
        for cell in spec["cells"]:
            for group in range(spec["groups_per_cell"]):
                source = root / "source" / f"{cell['case']}-{cell['support']}-{group}"
                audits = root / "audits" / f"{cell['case']}-{cell['support']}-{group}"
                output = (
                    workspace / spec["run_id"] / f"case-{cell['case']}"
                    / f"support-{cell['support']}" / f"group-{group}"
                )
                for offset in range(spec["workers_per_job"]):
                    shard = group * spec["workers_per_job"] + offset
                    write(source / f"shard-{shard}.json", {
                        "schema_version": 1,
                        "run_id": spec["run_id"],
                        "mode": "exact_support_layer",
                        "case": cell["case"],
                        "orbit": cell["orbit"],
                        "support": cell["support"],
                        "shard_id": shard,
                        "shard_count": spec["shard_count"],
                        "partition_version": spec["partition"],
                        "symmetry_breaking": True,
                        "partition_group_sizes": group_sizes,
                        "stabilizer_size": cell["stabilizer_size"],
                        "term_variables": cell["term_variables"],
                        "escape_variables": spec["expected_escape_variables"],
                        "status": "INFEASIBLE",
                        "complete_enumeration": True,
                        "hit_cap": False,
                        "hit_deadline": False,
                        "hit_signal": False,
                        "wall_seconds": 0.01,
                        "enumerated_supports": 0,
                        "raw_supports": 0,
                        "support_orbits": 0,
                        "orbits": [],
                    })
                    (source / f"shard-{shard}.exit").write_text("0\n", encoding="utf-8")
                    write(audits / f"audit-shard-{shard}.json", {
                        "schema_version": 1,
                        "run_id": spec["audit_run_id"],
                        "source_run": PIPELINE,
                        "source_logical_run": spec["run_id"],
                        "index": cell["case"],
                        "orbit": cell["orbit"],
                        "missing_type": cell["missing_type"],
                        "support": cell["support"],
                        "input_complete": True,
                        "audited_support_orbits": 0,
                        "two_sided_total": 0,
                        "two_sided_support_orbits": 0,
                        "two_sided_histogram": [{"two_sided": 0, "orbits": 0}],
                        "two_sided_samples": [],
                        "nonface_total": 0,
                        "nonface_support_orbits": 0,
                        "nonface_samples": [],
                        "all_force_zero": True,
                        "all_two_sided_are_coordinate_edge_faces": True,
                    })
                subprocess.run([
                    sys.executable, str(GROUP_SCRIPT),
                    "--spec", str(SPEC_PATH),
                    "--case", str(cell["case"]),
                    "--support", str(cell["support"]),
                    "--group", str(group),
                    "--input-dir", str(source),
                    "--audit-dir", str(audits),
                    "--output", str(output / "group-summary.json"),
                    "--survivor-dir", str(output / "survivors"),
                    "--pipeline-number", str(PIPELINE),
                    "--vcs-revision", REVISION,
                    ref_argument, ref_value,
                    "--resource-class", spec["resource_class"],
                ], check=True, stdout=subprocess.DEVNULL)
        archive = root / "archive"
        subprocess.run([
            sys.executable, str(COLLECT_SCRIPT),
            "--spec", str(SPEC_PATH),
            "--input-root", str(workspace),
            "--output-dir", str(archive),
            "--pipeline-number", str(PIPELINE),
            "--vcs-revision", REVISION,
            ref_argument, ref_value,
        ], check=True, stdout=subprocess.DEVNULL)
        summary = json.loads((archive / "summary.json").read_text(encoding="utf-8"))
        assert summary["accepted"] and summary["technical_completion"]
        assert summary["groups"] == 32 and summary["shards"] == 128
        assert summary["audited_support_orbits"] == 0 and summary["all_force_zero"]
        for line in (archive / "checksums.sha256").read_text(encoding="utf-8").splitlines():
            expected, name = line.split("  ", 1)
            actual = hashlib.sha256((archive / name).read_bytes()).hexdigest()
            assert actual == expected
    finally:
        for path in TEST_ROOT.iterdir():
            if path.name == ".gitignore":
                continue
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    print(f"{spec['run_id']}-contract-ok")


if __name__ == "__main__":
    main()
