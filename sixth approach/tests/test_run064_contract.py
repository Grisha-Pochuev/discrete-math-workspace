#!/usr/bin/env python3
"""Synthetic contract tests for grouped version-3 exact-cut shards."""

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
SPEC = SIXTH / "specs" / "run-064-adaptive-exact-cuts.json"
BUNDLE = SIXTH / "specs" / "run-064-exact-event-cuts.json"
HEADER = SIXTH / "run052_adaptive" / "exact_event_cuts_v3.h"


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


class Run064ContractTest(unittest.TestCase):
    def test_cut_table_complete_matrix_archive_and_unknown_rejection(self):
        spec = json.loads(SPEC.read_text(encoding="utf-8"))
        self.assertEqual(spec["exact_cut_version"], 3)
        self.assertEqual(spec["compute_jobs"], 48)
        self.assertEqual(spec["workers_per_job"], 4)
        self.assertEqual(spec["workers_per_shard"], 1)
        self.assertEqual(spec["jobs"], 192)
        run(
            SIXTH / "run064_cut_contract.py",
            "--bundle", BUNDLE,
            "--header", HEADER,
        )
        canonical_bundle = BUNDLE.read_text(encoding="utf-8").replace(
            "\r\n", "\n"
        ).encode()
        canonical_header = HEADER.read_text(encoding="utf-8").replace(
            "\r\n", "\n"
        ).encode()
        self.assertEqual(
            hashlib.sha256(canonical_bundle).hexdigest(),
            spec["cut_bundle_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(canonical_header).hexdigest(),
            spec["cut_header_sha256"],
        )
        bundle = json.loads(BUNDLE.read_text(encoding="utf-8"))
        self.assertEqual(len(bundle["cuts"]), 218)
        self.assertEqual(
            {graph: sum(cut["graph"] == graph for cut in bundle["cuts"])
             for graph in ("C8", "C5+C3", "C4+C4")},
            {"C8": 66, "C5+C3": 78, "C4+C4": 74},
        )

        with tempfile.TemporaryDirectory(dir=SIXTH) as temporary:
            root = Path(temporary)
            shards = root / "shards"
            for graph in spec["graphs"]:
                graph_root = shards / graph["id"]
                graph_root.mkdir(parents=True)
                for shard in range(spec["shards_per_graph"]):
                    (graph_root / f"shard-{shard}.json").write_text(
                        json.dumps(infeasible_record(spec, graph, shard)) + "\n",
                        encoding="utf-8",
                    )
                    (graph_root / f"shard-{shard}.exit").write_text(
                        "0\n", encoding="utf-8"
                    )

            summary = root / "summary.json"
            run(
                SIXTH / "run061_collect.py",
                "--spec", SPEC,
                "--input-root", shards,
                "--output", summary,
            )
            report = json.loads(summary.read_text(encoding="utf-8"))
            self.assertTrue(report["accepted"])
            self.assertTrue(report["mathematical_closure"])
            self.assertEqual(report["validated_shards"], 192)

            archive = root / "archive"
            run(
                SIXTH / "run061_archive.py",
                "--spec", SPEC,
                "--summary", summary,
                "--input-root", shards,
                "--output-dir", archive,
                "--workflow-run", "789",
                "--source-sha", "d" * 40,
            )
            with gzip.open(archive / "survivors.json.gz", "rt", encoding="utf-8") as stream:
                self.assertEqual(json.load(stream)["survivors"], [])
            for line in (archive / "checksums.sha256").read_text().splitlines():
                expected, name = line.split("  ", 1)
                actual = hashlib.sha256((archive / name).read_bytes()).hexdigest()
                self.assertEqual(actual, expected)

            graph = spec["graphs"][0]
            candidate = shards / graph["id"] / "shard-0.json"
            record = json.loads(candidate.read_text(encoding="utf-8"))
            record["status"] = "UNKNOWN"
            record["screen_state"] = "unknown"
            record["round_statuses"] = ["UNKNOWN"]
            candidate.write_text(json.dumps(record) + "\n", encoding="utf-8")
            (candidate.parent / "shard-0.exit").write_text("2\n", encoding="utf-8")
            incomplete = root / "incomplete.json"
            result = run(
                SIXTH / "run061_collect.py",
                "--spec", SPEC,
                "--input-root", shards,
                "--output", incomplete,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            rejected = json.loads(incomplete.read_text(encoding="utf-8"))
            self.assertFalse(rejected["accepted"])
            self.assertEqual(rejected["states"]["unknown"], 1)


if __name__ == "__main__":
    unittest.main()
