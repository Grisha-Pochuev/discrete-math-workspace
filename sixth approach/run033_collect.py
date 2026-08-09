"""Validate and merge four exact native shards for one support layer."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys


DEFAULT_RUN_ID = "run-033"
SHARD_COUNT = 4
PARTITION_VERSION = "parity2-v1"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--case", type=int, required=True)
    parser.add_argument("--orbit", type=int, required=True)
    parser.add_argument("--support", type=int, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-stabilizer", type=int)
    parser.add_argument("--expected-term-variables", type=int)
    parser.add_argument("--expected-escape-variables", type=int)
    parser.add_argument("--require-exit-files", action="store_true")
    args = parser.parse_args()
    errors = []
    workers = []
    merged = defaultdict(int)
    raw_total = 0
    for shard_id in range(SHARD_COUNT):
        path = args.input_dir / f"shard-{shard_id}.json"
        exit_path = args.input_dir / f"shard-{shard_id}.exit"
        if not path.exists():
            errors.append(f"missing {path.name}")
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"invalid {path.name}: {exc}")
            continue
        exit_code = None
        if exit_path.exists():
            try:
                exit_code = int(exit_path.read_text(encoding="utf-8").strip())
            except Exception as exc:
                errors.append(f"invalid {exit_path.name}: {exc}")
        elif args.require_exit_files:
            errors.append(f"missing {exit_path.name}")
        expected = {
            "run_id": args.run_id,
            "case": args.case,
            "orbit": args.orbit,
            "support": args.support,
            "shard_id": shard_id,
            "shard_count": SHARD_COUNT,
            "partition_version": PARTITION_VERSION,
        }
        for key, value in expected.items():
            if record.get(key) != value:
                errors.append(f"{path.name}: {key}={record.get(key)!r}, expected {value!r}")
        expected_model = {
            "stabilizer_size": args.expected_stabilizer,
            "term_variables": args.expected_term_variables,
            "escape_variables": args.expected_escape_variables,
        }
        for key, value in expected_model.items():
            if value is not None and record.get(key) != value:
                errors.append(f"{path.name}: {key}={record.get(key)!r}, expected {value!r}")
        if args.require_exit_files and exit_code != 0:
            errors.append(f"{path.name}: exit code {exit_code!r}")
        if not record.get("complete_enumeration"):
            errors.append(f"{path.name}: incomplete enumeration")
        if record.get("hit_cap") or record.get("hit_deadline") or record.get("hit_signal"):
            errors.append(f"{path.name}: stop flag is set")
        if record.get("status") not in ("OPTIMAL", "INFEASIBLE"):
            errors.append(f"{path.name}: nonterminal status {record.get('status')!r}")
        orbits = record.get("orbits", [])
        if len(orbits) != record.get("support_orbits"):
            errors.append(f"{path.name}: orbit count mismatch")
        multiplicity = sum(item.get("labelled_multiplicity", 0) for item in orbits)
        if multiplicity != record.get("raw_supports"):
            errors.append(f"{path.name}: multiplicity mismatch")
        for item in orbits:
            masks = tuple(item["masks"])
            if len(masks) != 8:
                errors.append(f"{path.name}: residual edge count mismatch")
                continue
            if any(not isinstance(mask, int) or not 0 < mask < 512 for mask in masks):
                errors.append(f"{path.name}: invalid mask")
                continue
            if sum(mask.bit_count() for mask in masks) != args.support:
                errors.append(f"{path.name}: support-size replay failed")
            expected_sizes = [mask.bit_count() for mask in masks]
            if item.get("edge_sizes") != expected_sizes:
                errors.append(f"{path.name}: edge-size replay failed")
            merged[masks] += item["labelled_multiplicity"]
        raw_total += record.get("raw_supports", 0)
        workers.append({
            "shard_id": shard_id,
            "exit_code": exit_code,
            "status": record.get("status"),
            "complete_enumeration": record.get("complete_enumeration"),
            "raw_supports": record.get("raw_supports"),
            "support_orbits": record.get("support_orbits"),
            "stabilizer_size": record.get("stabilizer_size"),
            "term_variables": record.get("term_variables"),
            "escape_variables": record.get("escape_variables"),
            "wall_seconds": record.get("wall_seconds"),
            "sha256": digest(path),
        })

    merged_orbits = [
        {
            "masks": list(masks),
            "edge_sizes": [mask.bit_count() for mask in masks],
            "labelled_multiplicity": multiplicity,
        }
        for masks, multiplicity in sorted(merged.items())
    ]
    if len(workers) != SHARD_COUNT:
        errors.append("worker count mismatch")
    if sum(item["labelled_multiplicity"] for item in merged_orbits) != raw_total:
        errors.append("merged multiplicity mismatch")
    result = {
        "schema_version": 1,
        "run_id": args.run_id,
        "mode": "exact_support_layer_merge",
        "case": args.case,
        "orbit": args.orbit,
        "support": args.support,
        "shard_count": SHARD_COUNT,
        "partition_version": PARTITION_VERSION,
        "status": "SUCCESS" if not errors else "INCOMPLETE",
        "complete_exact_coverage": not errors,
        "raw_supports": raw_total,
        "support_orbits": len(merged_orbits),
        "workers": sorted(workers, key=lambda item: item["shard_id"]),
        "errors": errors,
        "orbits": merged_orbits,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(args.output, result)
    print(json.dumps({key: value for key, value in result.items() if key != "orbits"}, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    sys.exit(main())
