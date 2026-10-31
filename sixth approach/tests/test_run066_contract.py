#!/usr/bin/env python3
"""Synthetic contracts for grouped version-6 exact-event shards."""

from __future__ import annotations

from collections import Counter
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
SPEC = SIXTH / "specs" / "run-066-adaptive-exact-cuts.json"
BASE_BUNDLE = SIXTH / "specs" / "run-065-exact-event-cuts.json"
ROW_BUNDLE = SIXTH / "specs" / "run-066-exact-row-cuts.json"
NEW_BUNDLE = SIXTH / "specs" / "run-066-exact-event-cuts.json"
BASE_HEADER = SIXTH / "run052_adaptive" / "exact_event_cuts_v4.h"
ROW_HEADER = SIXTH / "run052_adaptive" / "exact_event_cuts_v5.h"
NEW_HEADER = SIXTH / "run052_adaptive" / "exact_event_cuts_v6.h"
WORKER = SIXTH / "run052_adaptive" / "main.cpp"


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


class Run066ContractTest(unittest.TestCase):
    def test_cut_tables_complete_matrix_archive_and_unknown_rejection(self):
        spec = json.loads(SPEC.read_text(encoding="utf-8"))
        self.assertEqual(spec["run_id"], "run-066")
        self.assertEqual(spec["exact_cut_version"], 6)
        self.assertEqual(spec["compute_jobs"], 48)
        self.assertEqual(spec["max_parallel"], 20)
        self.assertTrue(spec["preflight_compile_gate"])
        self.assertEqual(spec["workers_per_job"], 4)
        self.assertEqual(spec["workers_per_shard"], 1)
        self.assertEqual(spec["jobs"], 192)
        self.assertEqual(spec["base_exact_event_cut_sources"], 396)
        self.assertEqual(spec["multirow_exact_event_cut_sources"], 43)
        self.assertEqual(spec["new_exact_event_cut_sources"], 185)
        self.assertEqual(spec["exact_event_cut_sources"], 624)

        run(SIXTH / "run065_cut_contract.py", "--bundle", BASE_BUNDLE,
            "--header", BASE_HEADER)
        run(SIXTH / "run066_cut_contract.py", "--bundle", ROW_BUNDLE,
            "--header", ROW_HEADER)
        run(SIXTH / "run066_exact_cut_contract.py", "--bundle", NEW_BUNDLE,
            "--header", NEW_HEADER)

        hashes = {
            BASE_BUNDLE: spec["base_cut_bundle_sha256"],
            ROW_BUNDLE: spec["row_cut_bundle_sha256"],
            NEW_BUNDLE: spec["cut_bundle_sha256"],
            BASE_HEADER: spec["cut_header_v4_sha256"],
            ROW_HEADER: spec["cut_header_v5_sha256"],
            NEW_HEADER: spec["cut_header_sha256"],
            WORKER: spec["worker_source_sha256"],
        }
        for path, expected in hashes.items():
            self.assertEqual(hashlib.sha256(canonical_bytes(path)).hexdigest(), expected)

        base = json.loads(BASE_BUNDLE.read_text(encoding="utf-8"))
        bundle = json.loads(ROW_BUNDLE.read_text(encoding="utf-8"))
        new_bundle = json.loads(NEW_BUNDLE.read_text(encoding="utf-8"))
        self.assertEqual(base["version"], 4)
        self.assertEqual(len(base["cuts"]), 396)
        self.assertEqual(bundle["version"], 5)
        self.assertEqual(bundle["semantics"],
                         "exact-event-conjunction-nogood-v2-multirow")
        self.assertEqual(len(bundle["cuts"]), 43)
        self.assertEqual(
            Counter(cut["graph"] for cut in bundle["cuts"]),
            {"C8": 19, "C5+C3": 7, "C4+C4": 17},
        )
        self.assertEqual(new_bundle["version"], 6)
        self.assertEqual(new_bundle["semantics"],
                         "exact-event-conjunction-nogood-v1")
        self.assertEqual(len(new_bundle["cuts"]), 185)
        self.assertEqual(
            Counter(cut["graph"] for cut in new_bundle["cuts"]),
            {"C8": 59, "C5+C3": 63, "C4+C4": 63},
        )

        base_counts = Counter(cut["graph"] for cut in base["cuts"])
        base_literals = Counter()
        for cut in base["cuts"]:
            base_literals[cut["graph"]] += 3 * len(cut["binomial_events"])
            target = cut.get("target_event")
            if target is not None:
                base_literals[cut["graph"]] += 1 + len(target["supported_matchings"])

        new_counts = Counter()
        new_literals = Counter()
        for index, cut in enumerate(bundle["cuts"]):
            self.assertEqual(cut["id"], f"laurent-event-cut-{index}")
            self.assertEqual(len({event["state"] for event in cut["row_events"]}),
                             len(cut["row_events"]))
            new_counts[cut["graph"]] += 1
            new_literals[cut["graph"]] += 3 * len(cut["binomial_events"])
            new_literals[cut["graph"]] += sum(
                1 + len(event["supported_matchings"])
                for event in cut["row_events"]
            )

        for index, cut in enumerate(new_bundle["cuts"]):
            self.assertEqual(cut["id"], f"exact-cut-v6-{index}")
            new_counts[cut["graph"]] += 1
            new_literals[cut["graph"]] += 3 * len(cut["binomial_events"])
            target = cut["target_event"]
            if target is not None:
                new_literals[cut["graph"]] += 1 + len(
                    target["supported_matchings"]
                )

        for graph in spec["graphs"]:
            name = graph["type"]
            self.assertEqual(graph["exact_event_cuts"],
                             base_counts[name] + new_counts[name])
            self.assertEqual(graph["exact_event_cut_literals"],
                             base_literals[name] + new_literals[name])

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
            run(SIXTH / "run061_collect.py", "--spec", SPEC,
                "--input-root", shards, "--output", summary)
            report = json.loads(summary.read_text(encoding="utf-8"))
            self.assertTrue(report["accepted"])
            self.assertTrue(report["mathematical_closure"])
            self.assertEqual(report["validated_shards"], 192)

            archive = root / "archive"
            run(SIXTH / "run061_archive.py", "--spec", SPEC,
                "--summary", summary, "--input-root", shards,
                "--output-dir", archive, "--workflow-run", "789",
                "--source-sha", "e" * 40)
            with gzip.open(archive / "survivors.json.gz", "rt",
                           encoding="utf-8") as stream:
                self.assertEqual(json.load(stream)["survivors"], [])
            for line in (archive / "checksums.sha256").read_text().splitlines():
                expected, name = line.split("  ", 1)
                self.assertEqual(
                    hashlib.sha256((archive / name).read_bytes()).hexdigest(), expected
                )

            graph = spec["graphs"][0]
            candidate = shards / graph["id"] / "shard-0.json"
            record = json.loads(candidate.read_text(encoding="utf-8"))
            record["status"] = "UNKNOWN"
            record["screen_state"] = "unknown"
            record["round_statuses"] = ["UNKNOWN"]
            candidate.write_text(json.dumps(record) + "\n", encoding="utf-8")
            (candidate.parent / "shard-0.exit").write_text("2\n", encoding="utf-8")
            incomplete = root / "incomplete.json"
            result = run(SIXTH / "run061_collect.py", "--spec", SPEC,
                         "--input-root", shards, "--output", incomplete,
                         check=False)
            self.assertNotEqual(result.returncode, 0)
            rejected = json.loads(incomplete.read_text(encoding="utf-8"))
            self.assertFalse(rejected["accepted"])
            self.assertEqual(rejected["states"]["unknown"], 1)


if __name__ == "__main__":
    unittest.main()
