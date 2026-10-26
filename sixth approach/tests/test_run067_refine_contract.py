#!/usr/bin/env python3
"""Synthetic contract for the single incomplete run-066 cell."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_run063_contract import infeasible_record, make_unknown, run


ROOT = Path(__file__).resolve().parents[2]
SIXTH = ROOT / "sixth approach"
BASE_SPEC = SIXTH / "specs" / "run-066-adaptive-exact-cuts.json"
RESCUE_SPEC = SIXTH / "specs" / "run-067-refine-one-cell.json"


class Run067RefineContractTest(unittest.TestCase):
    def test_exact_partition_identity_and_replacement(self):
        base = json.loads(BASE_SPEC.read_text(encoding="utf-8"))
        rescue = json.loads(RESCUE_SPEC.read_text(encoding="utf-8"))
        parent = rescue["parent"]
        children = rescue["refinement"]["child_shards"]
        self.assertEqual(children, [23, 87, 151, 215])
        self.assertTrue(all(child % 64 == 23 for child in children))

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            github_output = root / "github-output.txt"
            result = run(
                SIXTH / "run065_refine_contract.py",
                "--spec", RESCUE_SPEC,
                "--run-id", rescue["run_id"],
                "--github-output", github_output,
            )
            outputs = dict(
                line.split("=", 1)
                for line in github_output.read_text(encoding="utf-8").splitlines()
            )
            self.assertEqual(outputs["child_shards"], "23 87 151 215")
            self.assertEqual(outputs["parent_workflow_run"], "31430989911")
            self.assertEqual(outputs["parent_logical_run"], "run-066")
            self.assertEqual(outputs["graph_id"], "c5c3")
            self.assertIn('"cut_version": "6"', result.stdout)

            parent_root = root / "parent"
            for graph in base["graphs"]:
                graph_root = parent_root / graph["id"]
                graph_root.mkdir(parents=True)
                for shard in range(base["shards_per_graph"]):
                    record = infeasible_record(base, graph, shard)
                    exit_code = "0\n"
                    if graph["type"] == parent["graph_type"] and shard == parent["shard"]:
                        make_unknown(record)
                        exit_code = "2\n"
                    (graph_root / f"shard-{shard}.json").write_text(
                        json.dumps(record) + "\n", encoding="utf-8"
                    )
                    (graph_root / f"shard-{shard}.exit").write_text(
                        exit_code, encoding="utf-8"
                    )

            graph = next(item for item in base["graphs"] if item["type"] == parent["graph_type"])
            derived = {
                **base,
                "run_id": rescue["run_id"],
                "shards_per_graph": rescue["refinement"]["shard_count"],
                "partition_bits": rescue["refinement"]["partition_bits"],
            }
            refinement = root / "refinement" / graph["id"]
            refinement.mkdir(parents=True)
            for shard in children:
                record = infeasible_record(derived, graph, shard)
                (refinement / f"shard-{shard}.json").write_text(
                    json.dumps(record) + "\n", encoding="utf-8"
                )
                (refinement / f"shard-{shard}.exit").write_text(
                    "0\n", encoding="utf-8"
                )

            summary = root / "summary.json"
            run(
                SIXTH / "run063_refine_collect.py",
                "--spec", RESCUE_SPEC,
                "--base-spec", BASE_SPEC,
                "--parent-root", parent_root,
                "--refinement-root", root / "refinement",
                "--output", summary,
            )
            report = json.loads(summary.read_text(encoding="utf-8"))
            self.assertTrue(report["accepted"])
            self.assertEqual(report["validated_leaf_shards"], 195)
            self.assertEqual(report["replaced_parent"]["shard"], 23)
            self.assertEqual(report["states"], {"infeasible": 195})

            child = refinement / "shard-23.json"
            record = json.loads(child.read_text(encoding="utf-8"))
            make_unknown(record)
            child.write_text(json.dumps(record) + "\n", encoding="utf-8")
            (refinement / "shard-23.exit").write_text("2\n", encoding="utf-8")
            rejected_path = root / "rejected.json"
            rejected = run(
                SIXTH / "run063_refine_collect.py",
                "--spec", RESCUE_SPEC,
                "--base-spec", BASE_SPEC,
                "--parent-root", parent_root,
                "--refinement-root", root / "refinement",
                "--output", rejected_path,
                check=False,
            )
            self.assertNotEqual(rejected.returncode, 0)
            rejected_report = json.loads(rejected_path.read_text(encoding="utf-8"))
            self.assertFalse(rejected_report["accepted"])
            self.assertEqual(rejected_report["validated_leaf_shards"], 194)
            self.assertEqual(len(rejected_report["failures"]), 1)


if __name__ == "__main__":
    unittest.main()
