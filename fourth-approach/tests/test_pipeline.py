#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from canonicalize import (
    canonical_support,
    independent_exact_verification,
    process_candidate,
    variable_index,
)
from inventory import inventory_git_tree_shard
from schema import ValidationError, launch_from_spec, validate_launch, validate_spec


class PipelineTests(unittest.TestCase):
    def test_launch_validation(self) -> None:
        launch = validate_launch(
            {
                "schema_version": 1,
                "enabled": False,
                "run_index": 1,
                "task": "stage1_canonicalize_verify",
                "spec_path": "fourth-approach/run-specs/run-001-stage1-canonicalize-verify.json",
                "jobs": 20,
                "minimum_jobs": 20,
                "runtime_seconds": 20700,
                "max_attempts": 0,
                "nonce": "long-enough-nonce",
            }
        )
        self.assertEqual(launch["jobs"], 20)

    def test_rejects_unknown_task(self) -> None:
        with self.assertRaises(ValidationError):
            validate_launch(
                {
                    "schema_version": 1,
                    "enabled": False,
                    "run_index": 0,
                    "task": "unknown",
                    "spec_path": "fourth-approach/run-specs/x.json",
                    "jobs": 1,
                    "minimum_jobs": 1,
                    "runtime_seconds": 60,
                    "max_attempts": 0,
                    "nonce": "long-enough-nonce",
                }
            )

    def test_ready_stage1_spec_and_launch_agree(self) -> None:
        spec = validate_spec(
            {
                "schema_version": 1,
                "implementation_status": "ready",
                "run_index": 1,
                "task": "stage1_canonicalize_verify",
                "title": "x",
                "research_question": "x",
                "scientific_output": "x",
                "next_decision": "x",
                "next_spec_path": "fourth-approach/run-specs/run-002-stage2-minimize-certificates.json",
                "candidate_archives": [{"path": "third-approach-2.0/runs/x/top-candidates.json.gz", "run_id": 1}],
                "execution": {"jobs": 20, "minimum_jobs": 20, "runtime_seconds": 20700, "max_attempts": 0},
            },
            require_ready=True,
        )
        launch = launch_from_spec(
            "fourth-approach/run-specs/run-001-stage1-canonicalize-verify.json",
            spec,
            enabled=False,
            nonce="stage-one-disabled-test",
        )
        validate_spec(spec, launch, require_ready=True)
        self.assertFalse(launch["enabled"])

    def test_independent_exact_verification(self) -> None:
        # A mono equation with no active perfect matching is F=-1.  Coefficient -1
        # therefore gives the exact identity 1=(-1)F.
        support = [variable_index(0, 1, 0, 0)]
        candidate = {
            "candidate_id": "fixture-a",
            "exact_verified": True,
            "scope": "n=6,d=3,support-restricted-system",
            "support_size": 1,
            "support_variables": support,
            "equation_rows": [0],
            "multiplier_features": [[]],
            "column_descriptors": [[0, []]],
            "exact_rational_coefficients": [[[ -1, 1], [0, 1]]],
            "max_multiplier_degree": 0,
            "certificate_score": 0.0,
        }
        verified, error, metrics = independent_exact_verification(candidate)
        self.assertTrue(verified, error)
        self.assertEqual(metrics["nonzero_coefficients"], 1)
        record = process_candidate(candidate, "fixture.json.gz", 1, 0)
        self.assertEqual(record["status"], "verified_exact")
        self.assertTrue(record["canonical_support_id"])

    def test_symmetry_related_supports_canonicalize_together(self) -> None:
        first, _ = canonical_support([variable_index(0, 1, 0, 1), variable_index(2, 3, 2, 0)])
        second, _ = canonical_support([variable_index(4, 5, 1, 2), variable_index(0, 2, 0, 1)])
        # The second support is constructed with the same two disjoint edge/color
        # pattern after relabeling vertices and globally relabeling colors.
        self.assertEqual(first, second)

    def test_git_tree_inventory_is_complete_and_disjoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "third-approach-2.0/runs/run-000").mkdir(parents=True)
            (root / "third-approach-2.0/runs/run-000/summary.json").write_text(
                json.dumps({"accepted": True, "run_id": 123}), encoding="utf-8"
            )
            (root / "second-approach-2.0").mkdir()
            (root / "second-approach-2.0/a.txt").write_text("a", encoding="utf-8")
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "test"], check=True)
            subprocess.run(
                ["git", "-C", str(root), "config", "user.email", "test@example.com"],
                check=True,
            )
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "fixture"], check=True)
            spec = validate_spec(
                {
                    "schema_version": 1,
                    "run_index": 0,
                    "task": "stage0_source_inventory",
                    "title": "x",
                    "research_question": "x",
                    "scientific_output": "x",
                    "next_decision": "x",
                    "include_globs": ["third-approach-2.0/**/*", "second-approach-2.0/**/*"],
                    "exclude_globs": [],
                    "parse_summary_json": True,
                }
            )
            shards = [inventory_git_tree_shard(root, spec, index, 4) for index in range(4)]
            records = [record for shard in shards for record in shard["records"]]
            paths = [record["path"] for record in records]
            self.assertEqual(len(paths), 2)
            self.assertEqual(len(paths), len(set(paths)))
            summary_record = next(record for record in records if record["path"].endswith("summary.json"))
            self.assertTrue(summary_record["summary"]["accepted"])
            self.assertTrue(summary_record["content_id"].startswith("git-blob:"))


if __name__ == "__main__":
    unittest.main()
