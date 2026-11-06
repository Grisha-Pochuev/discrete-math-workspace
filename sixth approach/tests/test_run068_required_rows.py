#!/usr/bin/env python3
"""Synthetic contracts for the three required retained rows in run-068."""

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
from contextlib import contextmanager
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[2]
SIXTH = ROOT / "sixth approach"
SPEC = SIXTH / "specs" / "run-068-required-rows.json"
LEGACY_SPEC = SIXTH / "specs" / "run-066-adaptive-exact-cuts.json"
WORKER = SIXTH / "run068_required_rows" / "main.cpp"
CMAKE = SIXTH / "run068_required_rows" / "CMakeLists.txt"
VALIDATOR = SIXTH / "run061_validate_shard.py"


def run(*arguments, check=True):
    return subprocess.run(
        [sys.executable, *map(str, arguments)],
        cwd=ROOT,
        check=check,
        capture_output=True,
        text=True,
    )


def canonical_bytes(path: Path) -> bytes:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").encode()


def load_validator():
    module_spec = importlib.util.spec_from_file_location(
        "run061_validate_shard", VALIDATOR
    )
    assert module_spec is not None and module_spec.loader is not None
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


@contextmanager
def writable_tempdir():
    """Avoid restrictive Windows ACLs created by tempfile mode 0700."""
    path = SIXTH / f".run068-test-{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path)


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
        "required_uniform_targets": True,
        "required_rows": 3,
        "required_term_variables": 3 * graph["expected_matchings"],
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


class Run068RequiredRowsTest(unittest.TestCase):
    def test_legacy_infeasible_record_remains_valid(self):
        spec = json.loads(LEGACY_SPEC.read_text(encoding="utf-8"))
        graph = spec["graphs"][0]
        record = infeasible_record(spec, graph, 0)
        for key in (
            "required_uniform_targets",
            "required_rows",
            "required_term_variables",
        ):
            record.pop(key)
        with writable_tempdir() as root:
            output = root / "record.json"
            exit_path = root / "record.exit"
            output.write_text(json.dumps(record) + "\n", encoding="utf-8")
            exit_path.write_text("0\n", encoding="utf-8")
            result = load_validator().validate_record(
                spec, graph["type"], 0, output, exit_path
            )
            self.assertTrue(result["technical_complete"])
            self.assertFalse(result["scientific_survivor"])

    def test_required_rows_matrix_archive_and_rejection(self):
        spec = json.loads(SPEC.read_text(encoding="utf-8"))
        self.assertEqual(spec["run_id"], "run-068")
        self.assertTrue(spec["required_uniform_targets"])
        self.assertEqual(spec["required_uniform_target_rows"], 3)
        self.assertEqual(spec["jobs"], 192)
        self.assertEqual(spec["compute_jobs"], 48)
        self.assertEqual(spec["max_parallel"], 20)
        self.assertEqual(spec["workers_per_job"], 4)
        self.assertEqual(spec["workers_per_shard"], 1)
        self.assertEqual(
            hashlib.sha256(canonical_bytes(WORKER)).hexdigest(),
            spec["worker_source_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(canonical_bytes(CMAKE)).hexdigest(),
            spec["worker_cmake_sha256"],
        )
        for key in ("base_cut_bundle", "row_cut_bundle", "cut_bundle"):
            path = ROOT / spec[f"{key}_path"]
            self.assertEqual(
                hashlib.sha256(canonical_bytes(path)).hexdigest(),
                spec[f"{key}_sha256"],
            )

        validator = load_validator()
        for graph in spec["graphs"]:
            full_masks = [511] * 20
            colour_zero_masks = [1] * 20
            self.assertEqual(
                validator.uniform_matching_counts(graph["type"], full_masks),
                [graph["expected_matchings"]] * 3,
            )
            self.assertEqual(
                validator.uniform_matching_counts(
                    graph["type"], colour_zero_masks
                ),
                [graph["expected_matchings"], 0, 0],
            )

        with writable_tempdir() as root:
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
                "--workflow-run", "1068",
                "--source-sha", "f" * 40,
            )
            with gzip.open(
                archive / "survivors.json.gz", "rt", encoding="utf-8"
            ) as stream:
                self.assertEqual(json.load(stream)["survivors"], [])
            for line in (archive / "checksums.sha256").read_text().splitlines():
                expected, name = line.split("  ", 1)
                self.assertEqual(
                    hashlib.sha256((archive / name).read_bytes()).hexdigest(),
                    expected,
                )

            candidate = shards / spec["graphs"][0]["id"] / "shard-0.json"
            record = json.loads(candidate.read_text(encoding="utf-8"))
            record["required_term_variables"] -= 1
            candidate.write_text(json.dumps(record) + "\n", encoding="utf-8")
            rejected_path = root / "rejected.json"
            rejected = run(
                SIXTH / "run061_collect.py",
                "--spec", SPEC,
                "--input-root", shards,
                "--output", rejected_path,
                check=False,
            )
            self.assertNotEqual(rejected.returncode, 0)


if __name__ == "__main__":
    unittest.main()
