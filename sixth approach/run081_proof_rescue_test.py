#!/usr/bin/env python3
"""Dependency-free contract tests for the targeted proof rescue."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


def load_module(path):
    spec = importlib.util.spec_from_file_location("run081_proof_rescue_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def terminal(module, spec, depth, prefix):
    record = {
        "depth": depth,
        "prefix": prefix,
        "node": module.node_name(depth, prefix),
        "prefix_literals": list(module.prefix_literals(spec, depth, prefix)),
        "state": "UNSAT_CERTIFIED",
        "solver_exit": 20,
        "checker_exit": 0,
        "checker_verified": True,
        "proof_file": f"proofs/{module.node_name(depth, prefix)}.lrat.gz",
        "proof_uncompressed_bytes": 1,
        "proof_uncompressed_sha256": "0" * 64,
        "proof_compressed_bytes": 1,
        "proof_compressed_sha256": "1" * 64,
    }
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    args = parser.parse_args()
    module = load_module(args.script.resolve())
    spec = module.load_spec(args.spec.resolve())
    temporary = args.script.resolve().parent
    try:
        all_roots = [
            root for lane in range(spec["lane_count"])
            for root in module.lane_roots(spec, lane)
        ]
        assert sorted(all_roots) == list(range(spec["root_count"]))

        # The 256 logical roots are exactly the leaves omitted by the four
        # incomplete parent lanes: eight depth-seven prefixes times 32 leaves.
        base_leaves = module.base_leaf_ids(spec)
        expected_base_leaves = tuple(sorted({
            parent | (suffix << spec["parent_prefix_depth"])
            for parent in spec["parent_prefixes"]
            for suffix in range(
                1 << (spec["base_assignment_depth"] - spec["parent_prefix_depth"])
            )
        }))
        assert base_leaves == expected_base_leaves
        assert len(base_leaves) == spec["parent_missing_leaf_count"] == 256
        for root_index, base_leaf in enumerate(base_leaves):
            literals = module.prefix_literals(spec, spec["root_depth"], root_index)
            assert len(literals) == spec["base_assignment_depth"]
            assert literals == tuple(
                variable if (base_leaf >> bit) & 1 else -variable
                for bit, variable in enumerate(spec["base_partition_variables"])
            )

        # Refinement is a true disjoint Boolean partition: every logical leaf
        # has a unique full tuple of 12 parent and eight rescue literals.
        full_literal_tuples = {
            module.prefix_literals(spec, spec["maximum_depth"], leaf)
            for leaf in range(spec["leaf_count"])
        }
        assert len(full_literal_tuples) == spec["leaf_count"]
        assert all(
            len(literals)
            == spec["base_assignment_depth"] + len(spec["split_variables"])
            for literals in full_literal_tuples
        )

        source = args.script.read_text(encoding="utf-8")
        assert '"--lrat", "--no-binary"' in source
        assert "--checkproof" not in source

        # A complete cover can mix depths without overlap: refine the first
        # root once and leave all other roots at root depth.
        records = []
        for root in range(spec["root_count"]):
            if root == 0:
                records.append(terminal(module, spec, spec["root_depth"] + 1, 0))
                records.append(terminal(
                    module, spec, spec["root_depth"] + 1,
                    1 << spec["root_depth"],
                ))
            else:
                records.append(terminal(module, spec, spec["root_depth"], root))
        covered, duplicates = module.covered_leaves(spec, records)
        assert not duplicates
        assert covered == set(range(spec["leaf_count"]))

        # Reusing a descendant underneath an accepted root is detected.
        bad = list(records)
        bad.append(terminal(module, spec, spec["root_depth"] + 1, 2))
        _, duplicates = module.covered_leaves(spec, bad)
        assert duplicates

        # Every logical refinement maps to exactly one prefix in the good cover.
        for leaf in range(spec["leaf_count"]):
            hits = [
                record for record in records
                if leaf & ((1 << record["depth"]) - 1) == record["prefix"]
            ]
            assert len(hits) == 1

        # Lane validation accepts metadata-only collection when the actual
        # proof payload is deliberately kept in a separate artifact.
        lane = 0
        lane_records = [
            terminal(module, spec, spec["root_depth"], root)
            for root in module.lane_roots(spec, lane)
        ]
        attempts = [module.public_attempt(record) for record in lane_records]
        payload = module.lane_payload(
            spec, lane, attempts, lane_records, True, False, None
        )
        module.validate_lane(
            spec, payload, lane, temporary,
            require_proof_payload=False,
        )

        # A valid mixed-depth DFS has the first root refined, with both
        # children terminal, and the second assigned root terminal.
        lane_root_values = module.lane_roots(spec, lane)
        first_root, second_root = lane_root_values[:2]
        refined = {
            "depth": spec["root_depth"],
            "prefix": first_root,
            "node": module.node_name(spec["root_depth"], first_root),
            "prefix_literals": list(module.prefix_literals(
                spec, spec["root_depth"], first_root
            )),
            "state": "REFINED_SOLVER_LIMIT",
            "solver_exit": 124,
        }
        child0 = terminal(module, spec, spec["root_depth"] + 1, first_root)
        child1 = terminal(
            module, spec, spec["root_depth"] + 1,
            first_root | (1 << spec["root_depth"]),
        )
        remaining_roots = [
            terminal(module, spec, spec["root_depth"], root)
            for root in lane_root_values[1:]
        ]
        mixed_attempts = [
            module.public_attempt(record)
            for record in (refined, child0, child1, *remaining_roots)
        ]
        mixed_payload = module.lane_payload(
            spec, lane, mixed_attempts, [child0, child1, *remaining_roots],
            True, False, None,
        )
        module.validate_lane(
            spec, mixed_payload, lane, temporary,
            require_proof_payload=False,
        )

        overlap_rejected_by_validator = False
        bad_records = lane_records + [terminal(
            module, spec, spec["root_depth"] + 1, lane_records[0]["prefix"]
        )]
        bad_payload = module.lane_payload(
            spec, lane,
            [module.public_attempt(record) for record in bad_records],
            bad_records, True, False, None,
        )
        try:
            module.validate_lane(
                spec, bad_payload, lane, temporary,
                require_proof_payload=False,
            )
        except ValueError:
            overlap_rejected_by_validator = True
        assert overlap_rejected_by_validator

        print(json.dumps({
            "accepted": True,
            "roots": len(all_roots),
            "leaves": len(covered),
            "base_parent_leaves": len(base_leaves),
            "full_literal_tuples": len(full_literal_tuples),
            "mixed_depth_cover_records": len(records),
            "overlap_rejected": True,
            "metadata_only_lane_accepted": True,
            "validator_overlap_rejected": True,
        }, sort_keys=True))
    finally:
        pass


if __name__ == "__main__":
    main()
