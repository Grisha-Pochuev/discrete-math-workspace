#!/usr/bin/env python3
"""Strict collector for the run-038 exact audit matrix."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--input-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    expected = {(item["index"], item["support"]) for item in spec["layers"]}
    if len(expected) != 15:
        raise ValueError("spec must declare exactly fifteen distinct layers")
    found = {}
    for path in args.input_root.rglob("audit.json"):
        item = json.loads(path.read_text(encoding="utf-8"))
        key = (item.get("index"), item.get("support"))
        if key in found:
            raise ValueError(f"duplicate audit for {key}")
        if item.get("run_id") != spec["run_id"] or item.get("source_run") != spec["source_run"]:
            raise ValueError(f"source identity mismatch for {key}")
        if not item.get("input_complete"):
            raise ValueError(f"incomplete audit for {key}")
        audited = item.get("audited_support_orbits")
        histogram = item.get("two_sided_histogram")
        if not isinstance(audited, int) or audited < 0 or not isinstance(histogram, list):
            raise ValueError(f"invalid audit totals for {key}")
        histogram_pairs = []
        for entry in histogram:
            if not isinstance(entry, dict):
                raise ValueError(f"invalid histogram row for {key}")
            two_sided, orbits = entry.get("two_sided"), entry.get("orbits")
            if not isinstance(two_sided, int) or not isinstance(orbits, int) or two_sided < 0 or orbits < 0:
                raise ValueError(f"invalid histogram values for {key}")
            histogram_pairs.append((two_sided, orbits))
        if len({two_sided for two_sided, _ in histogram_pairs}) != len(histogram_pairs):
            raise ValueError(f"duplicate histogram bin for {key}")
        if sum(orbits for _, orbits in histogram_pairs) != audited:
            raise ValueError(f"histogram coverage mismatch for {key}")
        total = sum(two_sided * orbits for two_sided, orbits in histogram_pairs)
        if total != item.get("two_sided_total"):
            raise ValueError(f"histogram total mismatch for {key}")
        positive = sum(orbits for two_sided, orbits in histogram_pairs if two_sided > 0)
        if positive != item.get("two_sided_support_orbits"):
            raise ValueError(f"survivor-orbit total mismatch for {key}")
        nonface_total = item.get("nonface_total")
        nonface_orbits = item.get("nonface_support_orbits")
        if not isinstance(nonface_total, int) or not isinstance(nonface_orbits, int):
            raise ValueError(f"invalid non-face totals for {key}")
        if not (0 <= nonface_orbits <= positive and 0 <= nonface_total <= total):
            raise ValueError(f"inconsistent non-face totals for {key}")
        if item.get("all_force_zero") != (total == 0):
            raise ValueError(f"zero-closure flag mismatch for {key}")
        if item.get("all_two_sided_are_coordinate_edge_faces") != (nonface_total == 0):
            raise ValueError(f"face flag mismatch for {key}")
        found[key] = item
    if set(found) != expected:
        raise ValueError(f"audit coverage mismatch; missing={sorted(expected - set(found))}; extra={sorted(set(found) - expected)}")
    two_sided_total = sum(item["two_sided_total"] for item in found.values())
    nonface_total = sum(item["nonface_total"] for item in found.values())
    summary = {
        "schema_version": 1,
        "run_id": spec["run_id"],
        "source_run": spec["source_run"],
        "accepted": True,
        "audited_layers": len(found),
        "audited_support_orbits": sum(item["audited_support_orbits"] for item in found.values()),
        "two_sided_total": two_sided_total,
        "two_sided_support_orbits": sum(item["two_sided_support_orbits"] for item in found.values()),
        "nonface_total": nonface_total,
        "nonface_support_orbits": sum(item["nonface_support_orbits"] for item in found.values()),
        "all_force_zero": two_sided_total == 0,
        "all_two_sided_are_coordinate_edge_faces": nonface_total == 0,
        "layers": [
            {
                "index": index,
                "support": support,
                "support_orbits": found[(index, support)]["audited_support_orbits"],
                "two_sided_total": found[(index, support)]["two_sided_total"],
                "nonface_total": found[(index, support)]["nonface_total"],
                "all_force_zero": found[(index, support)]["all_force_zero"],
            }
            for index, support in sorted(found)
        ],
    }
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
