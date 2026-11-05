#!/usr/bin/env python3
"""Check that the compiled version-3 event table matches its bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


MAX_BINOMIALS = 8
MAX_TARGET_TERMS = 6


def canonical_bytes(path: Path) -> bytes:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").encode()


def render(bundle_path: Path) -> str:
    raw = canonical_bytes(bundle_path)
    bundle = json.loads(raw)
    assert bundle["schema_version"] == 1
    assert bundle["version"] == 3
    assert bundle["semantics"] == "exact-event-conjunction-nogood-v1"
    assert bundle["base_version"] == 2
    assert len(bundle["cuts"]) == 218
    bundle_sha256 = hashlib.sha256(raw).hexdigest()
    result = [
        "#pragma once\n\n",
        "#include <array>\n",
        "#include <string_view>\n\n",
        "namespace exact_event_cuts_v3 {\n\n",
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
        f"inline constexpr std::array<Cut, {len(bundle['cuts'])}> kVersion3{{{{\n",
    ]
    for index, cut in enumerate(bundle["cuts"]):
        assert cut["id"] == f"exact-cut-v3-{index}"
        events = cut["binomial_events"]
        assert 1 <= len(events) <= MAX_BINOMIALS
        padded_events = [
            f'{{{event["state"]}, {event["left"]}, {event["right"]}}}'
            for event in events
        ] + ["{-1, -1, -1}"] * (MAX_BINOMIALS - len(events))
        target = cut["target_event"]
        if target is None:
            target_state = -1
            targets = []
        else:
            target_state = target["state"]
            targets = target["supported_matchings"]
            assert 3 <= len(targets) <= MAX_TARGET_TERMS
        padded_targets = targets + [-1] * (MAX_TARGET_TERMS - len(targets))
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
    result.extend([
        "}};\n\n",
        "}  // namespace exact_event_cuts_v3\n",
    ])
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
        "cuts": 218,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
