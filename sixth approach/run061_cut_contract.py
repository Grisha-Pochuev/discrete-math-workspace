#!/usr/bin/env python3
"""Check that the compiled exact-event table matches its canonical bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def render(bundle_path: Path) -> str:
    raw = bundle_path.read_bytes()
    bundle = json.loads(raw)
    assert bundle["schema_version"] == bundle["version"] == 1
    assert bundle["semantics"] == "exact-event-conjunction-nogood-v1"
    assert len(bundle["cuts"]) == 4
    bundle_sha256 = hashlib.sha256(raw).hexdigest()
    result = [
        "#pragma once\n\n",
        "#include <array>\n",
        "#include <string_view>\n\n",
        "namespace exact_event_cuts {\n\n",
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
        "  std::array<BinomialEvent, 3> binomials;\n",
        "  bool has_target;\n",
        "  int target_state;\n",
        "  std::array<int, 3> target_matchings;\n",
        "};\n\n",
        "// Compact, independently audited event no-goods.  A binomial event means that\n",
        "// the named row has exactly two supported terms and they are the named pair.\n",
        "// A target event means that the named row has exactly the three named terms.\n",
        "inline constexpr std::array<Cut, 4> kVersion1{{\n",
    ]
    for index, cut in enumerate(bundle["cuts"]):
        assert cut["id"] == f"exact-cut-{index}"
        assert len(cut["binomial_events"]) == 3
        target = cut["target_event"]
        if target is not None:
            assert len(target["supported_matchings"]) == 3
        events = ", ".join(
            f'{{{event["state"]}, {event["left"]}, {event["right"]}}}'
            for event in cut["binomial_events"]
        )
        target_state = -1 if target is None else target["state"]
        target_matchings = (
            [-1, -1, -1] if target is None else target["supported_matchings"]
        )
        result.extend([
            "    {\n",
            f'        "{cut["graph"]}",\n',
            f'        {cut["source_shard"]},\n',
            "        {{" + events + "}},\n",
            f'        {"true" if target is not None else "false"},\n',
            f"        {target_state},\n",
            "        {{" + ", ".join(map(str, target_matchings)) + "}},\n",
            "    },\n",
        ])
    result.extend([
        "}};\n\n",
        "}  // namespace exact_event_cuts\n",
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
        actual = args.header.read_text(encoding="utf-8")
        assert actual == expected, "generated exact-event header is stale"
    print(json.dumps({
        "status": "accepted",
        "bundle_sha256": hashlib.sha256(args.bundle.read_bytes()).hexdigest(),
        "header_sha256": hashlib.sha256(expected.encode()).hexdigest(),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
