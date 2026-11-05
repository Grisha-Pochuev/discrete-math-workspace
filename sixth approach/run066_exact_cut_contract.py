#!/usr/bin/env python3
"""Check that the compiled version-6 event table matches its proof-free bundle."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re


MAX_BINOMIALS = 9
MAX_TARGET_TERMS = 7
MATCHING_LIMITS = {"C8": 31, "C5+C3": 30, "C4+C4": 33}
EXPECTED_COUNTS = {"C8": 59, "C5+C3": 63, "C4+C4": 63}
EXPECTED_LITERALS = {"C8": 560, "C5+C3": 647, "C4+C4": 673}


def canonical_bytes(path: Path) -> bytes:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").encode()


def render(bundle_path: Path) -> str:
    raw = canonical_bytes(bundle_path)
    bundle = json.loads(raw)
    assert bundle["schema_version"] == 1
    assert bundle["version"] == 6
    assert bundle["semantics"] == "exact-event-conjunction-nogood-v1"
    assert bundle["source_run"] == "run-065-r1"
    assert bundle["source_github_run"] == 31422138690
    assert re.fullmatch(r"[0-9a-f]{64}", bundle["private_proof_bundle_sha256"])
    assert re.fullmatch(r"[0-9a-f]{64}", bundle["independent_audit_sha256"])
    assert len(bundle["cuts"]) == 185
    bundle_sha256 = hashlib.sha256(raw).hexdigest()
    result = [
        "#pragma once\n\n",
        "#include <array>\n",
        "#include <string_view>\n\n",
        "namespace exact_event_cuts_v6 {\n\n",
        "inline constexpr std::string_view kBundleSha256 =\n",
        f'    "{bundle_sha256}";\n\n',
        "struct BinomialEvent {\n",
        "  int state;\n",
        "  int left;\n",
        "  int right;\n",
        "};\n\n",
        "struct Cut {\n",
        "  std::string_view graph;\n",
        "  int source_shard;\n",
        "  int binomial_count;\n",
        f"  std::array<BinomialEvent, {MAX_BINOMIALS}> binomials;\n",
        "  int target_state;\n",
        "  int target_count;\n",
        f"  std::array<int, {MAX_TARGET_TERMS}> target_matchings;\n",
        "};\n\n",
        "// Independently audited exact-event conjunction no-goods.\n",
        f"inline constexpr std::array<Cut, {len(bundle['cuts'])}> kVersion6{{{{\n",
    ]
    graph_counts = Counter()
    graph_literals = Counter()
    source_keys = set()
    fingerprints = set()
    for index, cut in enumerate(bundle["cuts"]):
        assert cut["id"] == f"exact-cut-v6-{index}"
        assert cut["graph"] in MATCHING_LIMITS
        assert cut["source_run"] == "run-065-r1"
        assert cut["source_record_run"] in {"run-065", "run-065-r1"}
        assert cut["source_leaf"] in {"parent", "refinement"}
        assert (cut["source_record_run"], cut["source_leaf"]) in {
            ("run-065", "parent"), ("run-065-r1", "refinement")
        }
        assert isinstance(cut["source_shard"], int) and cut["source_shard"] >= 0
        assert re.fullmatch(r"[0-9a-f]{64}", cut["source_sha256"])
        source_key = (
            cut["source_record_run"], cut["source_leaf"], cut["graph"],
            cut["source_shard"], cut["source_sha256"],
        )
        assert source_key not in source_keys
        source_keys.add(source_key)
        events = cut["binomial_events"]
        assert 1 <= len(events) <= MAX_BINOMIALS
        assert len({(e["state"], e["left"], e["right"]) for e in events}) == len(events)
        padded_events = []
        for event in events:
            assert 0 <= event["state"] < 3**8
            assert 0 <= event["left"] < event["right"] < MATCHING_LIMITS[cut["graph"]]
            padded_events.append(
                f'{{{event["state"]}, {event["left"]}, {event["right"]}}}'
            )
        padded_events += ["{-1, -1, -1}"] * (MAX_BINOMIALS - len(events))

        target = cut["target_event"]
        if target is None:
            target_state = -1
            targets = []
        else:
            target_state = target["state"]
            targets = target["supported_matchings"]
            assert 3 <= len(targets) <= MAX_TARGET_TERMS
            assert targets == sorted(set(targets))
            assert 0 <= target_state < 3**8
            assert all(0 <= item < MATCHING_LIMITS[cut["graph"]] for item in targets)
        padded_targets = targets + [-1] * (MAX_TARGET_TERMS - len(targets))
        fingerprint = json.dumps(
            {
                "graph": cut["graph"],
                "binomial_events": events,
                "target_event": target,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        assert fingerprint not in fingerprints
        fingerprints.add(fingerprint)
        graph_counts[cut["graph"]] += 1
        graph_literals[cut["graph"]] += 3 * len(events)
        if target is not None:
            graph_literals[cut["graph"]] += 1 + len(targets)
        result.extend([
            "    {\n",
            f'        "{cut["graph"]}",\n',
            f'        {cut["source_shard"]},\n',
            f"        {len(events)},\n",
            "        {{" + ", ".join(padded_events) + "}},\n",
            f"        {target_state},\n",
            f"        {len(targets)},\n",
            "        {{" + ", ".join(map(str, padded_targets)) + "}},\n",
            "    },\n",
        ])
    assert graph_counts == EXPECTED_COUNTS
    assert graph_literals == EXPECTED_LITERALS
    result.extend(["}};\n\n", "}  // namespace exact_event_cuts_v6\n"])
    return "".join(result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--header", required=True, type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    expected = render(args.bundle)
    if args.write:
        args.header.write_text(expected, encoding="utf-8", newline="\n")
    else:
        assert args.header.read_text(encoding="utf-8") == expected
    print(json.dumps({
        "status": "accepted",
        "bundle_sha256": hashlib.sha256(canonical_bytes(args.bundle)).hexdigest(),
        "header_sha256": hashlib.sha256(expected.encode()).hexdigest(),
        "cuts": 185,
        "literals": sum(EXPECTED_LITERALS.values()),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
