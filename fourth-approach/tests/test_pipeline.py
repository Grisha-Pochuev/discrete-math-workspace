#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from inventory import inventory_git_tree_shard
from schema import ValidationError, validate_launch, validate_spec


class PipelineTests(unittest.TestCase):
    def test_launch_validation(self) -> None:
        launch = validate_launch(
            {
                "schema_version": 1,
                "enabled": False,
                "run_index": 0,
                "task": "stage0_source_inventory",
                "spec_path": "fourth-approach/run-specs/run-000-stage0-source-inventory.json",
                "jobs": 4,
                "minimum_jobs": 4,
                "runtime_seconds": 900,
                "max_attempts": 0,
                "nonce": "long-enough-nonce",
            }
        )
        self.assertEqual(launch["jobs"], 4)

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
            shards = [inventory_git_tree_shard(root, spec, i, 4) for i in range(4)]
            records = [record for shard in shards for record in shard["records"]]
            paths = [record["path"] for record in records]
            self.assertEqual(len(paths), 2)
            self.assertEqual(len(paths), len(set(paths)))
            summary_record = next(record for record in records if record["path"].endswith("summary.json"))
            self.assertTrue(summary_record["summary"]["accepted"])
            self.assertTrue(summary_record["content_id"].startswith("git-blob:"))


if __name__ == "__main__":
    unittest.main()
