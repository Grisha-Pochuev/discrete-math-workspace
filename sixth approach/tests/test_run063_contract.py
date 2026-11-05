#!/usr/bin/env python3
"""Synthetic contract tests for one-cell adaptive refinement."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SIXTH = ROOT / "sixth approach"
BASE_SPEC = SIXTH / "specs" / "run-062-adaptive-exact-cuts.json"
RESCUE_SPEC = SIXTH / "specs" / "run-063-refine-one-cell.json"


def run(*arguments, check=True):
    return subprocess.run(
        [sys.executable, *map(str, arguments)],
        cwd=ROOT,
        check=check,
        capture_output=True,
        text=True,
    )


def infeasible_record(spec, graph, shard):
    return {
        "schema_version": 1,
        "run_id": spec["run_id"],
        "graph": graph["type"],
        "status": "INFEASIBLE",
        "screen_state": "infeasible",
        "solve_rounds": 1,
        "requested_exchange_rounds": spec["exchange_rounds"],
        "seconds_per_round": spec["seconds_per_round"],
        "workers": spec["workers_per_shard"],
        "memory_mib": spec["worker_memory_mib"],
        "shard_id": shard,
        "shard_count": spec["shards_per_graph"],
        "partition": spec["partition"],
        "exact_cut_version": spec["exact_cut_version"],
        "exact_event_cut_bundle_sha256": spec["cut_bundle_sha256"],
        "exact_event_cuts": graph["exact_event_cuts"],
        "exact_event_cut_literals": graph["exact_event_cut_literals"],
        "wall_seconds": 0.25,
        "branches": 0,
        "conflicts": 0,
        "perfect_matchings": graph["expected_matchings"],
        "mixed_rows": 6558,
        "term_variables": 6558 * graph["expected_matchings"],
        "support_variables": 180,
        "anchor_variables": 120,
        "anchor_support_variables": 72,
        "noncoordinate_variables": 24,
        "assignment_variables": 120,
        "assignment_column_variables": 240,
        "learned_binomial_events": 0,
        "learned_trinomial_events": 0,
        "learned_ratio_classes": 0,
        "direct_exchange_contradictions": 0,
        "round_statuses": ["INFEASIBLE"],
        "round_wall_seconds": [0.25],
    }


def make_unknown(record):
    record["status"] = "UNKNOWN"
    record["screen_state"] = "unknown"
    record["round_statuses"] = ["UNKNOWN"]
    record["wall_seconds"] = 120.0
    record["round_wall_seconds"] = [120.0]


class Run063ContractTest(unittest.TestCase):
    def test_exact_replacement_archive_and_unknown_rejection(self):
        base = json.loads(BASE_SPEC.read_text(encoding="utf-8"))
        rescue = json.loads(RESCUE_SPEC.read_text(encoding="utf-8"))
        self.assertEqual(rescue["compute_jobs"], 1)
        self.assertEqual(rescue["workers_per_job"], 4)
        self.assertEqual(rescue["workers_per_shard"], 1)
        self.assertEqual(rescue["refinement"]["child_shards"], [31, 95, 159, 223])
        self.assertTrue(all(shard % 64 == 31 for shard in rescue["refinement"]["child_shards"]))

        with tempfile.TemporaryDirectory(dir=SIXTH) as temporary:
            root = Path(temporary)
            parent = root / "parent"
            for graph in base["graphs"]:
                graph_root = parent / graph["id"]
                graph_root.mkdir(parents=True)
                for shard in range(base["shards_per_graph"]):
                    record = infeasible_record(base, graph, shard)
                    exit_code = "0\n"
                    if graph["type"] == "C4+C4" and shard == 31:
                        make_unknown(record)
                        exit_code = "2\n"
                    (graph_root / f"shard-{shard}.json").write_text(
                        json.dumps(record) + "\n", encoding="utf-8"
                    )
                    (graph_root / f"shard-{shard}.exit").write_text(
                        exit_code, encoding="utf-8"
                    )

            graph = next(item for item in base["graphs"] if item["type"] == "C4+C4")
            derived = {
                **base,
                "run_id": rescue["run_id"],
                "shards_per_graph": rescue["refinement"]["shard_count"],
                "partition_bits": rescue["refinement"]["partition_bits"],
                "seconds_per_round": rescue["seconds_per_round"],
                "exchange_rounds": rescue["exchange_rounds"],
            }
            refinement = root / "refinement" / graph["id"]
            refinement.mkdir(parents=True)
            for shard in rescue["refinement"]["child_shards"]:
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
                "--parent-root", parent,
                "--refinement-root", root / "refinement",
                "--output", summary,
            )
            report = json.loads(summary.read_text(encoding="utf-8"))
            self.assertTrue(report["accepted"])
            self.assertTrue(report["mathematical_closure"])
            self.assertEqual(report["validated_leaf_shards"], 195)
            self.assertEqual(report["states"], {"infeasible": 195})
            self.assertEqual(report["replaced_parent"]["screen_state"], "unknown")

            archive = root / "archive"
            run(
                SIXTH / "run063_refine_archive.py",
                "--spec", RESCUE_SPEC,
                "--base-spec", BASE_SPEC,
                "--summary", summary,
                "--parent-root", parent,
                "--refinement-root", root / "refinement",
                "--output-dir", archive,
                "--workflow-run", "456",
                "--source-sha", "c" * 40,
            )
            with gzip.open(archive / "survivors.json.gz", "rt", encoding="utf-8") as stream:
                self.assertEqual(json.load(stream)["survivors"], [])
            for line in (archive / "checksums.sha256").read_text().splitlines():
                expected, name = line.split("  ", 1)
                actual = hashlib.sha256((archive / name).read_bytes()).hexdigest()
                self.assertEqual(actual, expected)

            child = refinement / "shard-31.json"
            record = json.loads(child.read_text(encoding="utf-8"))
            make_unknown(record)
            child.write_text(json.dumps(record) + "\n", encoding="utf-8")
            (refinement / "shard-31.exit").write_text("2\n", encoding="utf-8")
            incomplete = root / "incomplete.json"
            result = run(
                SIXTH / "run063_refine_collect.py",
                "--spec", RESCUE_SPEC,
                "--base-spec", BASE_SPEC,
                "--parent-root", parent,
                "--refinement-root", root / "refinement",
                "--output", incomplete,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            rejected = json.loads(incomplete.read_text(encoding="utf-8"))
            self.assertFalse(rejected["accepted"])
            self.assertEqual(rejected["validated_leaf_shards"], 194)
            self.assertEqual(len(rejected["failures"]), 1)


if __name__ == "__main__":
    unittest.main()
