#!/usr/bin/env python3
"""Check that the compiled version-5 multi-row event table matches its bundle."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re


MAX_BINOMIALS = 9
MAX_ROW_EVENTS = 31
MAX_ROW_TERMS = 11
MATCHING_LIMITS = {"C8": 31, "C5+C3": 30, "C4+C4": 33}
EXPECTED_NEW_LITERALS = {"C8": 654, "C5+C3": 170, "C4+C4": 524}


def canonical_bytes(path: Path) -> bytes:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").encode()


def render(bundle_path: Path) -> str:
    raw = canonical_bytes(bundle_path)
    bundle = json.loads(raw)
    assert bundle["schema_version"] == 1
    assert bundle["version"] == 5
    assert bundle["semantics"] == "exact-event-conjunction-nogood-v2-multirow"
    assert len(bundle["cuts"]) == 43
    bundle_sha256 = hashlib.sha256(raw).hexdigest()
    result = [
        "#pragma once\n\n",
        "#include <array>\n",
        "#include <string_view>\n\n",
        "namespace exact_event_cuts_v5 {\n\n",
        "inline constexpr std::string_view kBundleSha256 =\n",
        f'    "{bundle_sha256}";\n\n',
        "struct BinomialEvent {\n",
        "  int state;\n",
        "  int left;\n",
        "  int right;\n",
        "};\n\n",
        "struct RowEvent {\n",
        "  int state;\n",
        "  int matching_count;\n",
        f"  std::array<int, {MAX_ROW_TERMS}> matchings;\n",
        "};\n\n",
        "struct Cut {\n",
        "  std::string_view graph;\n",
        "  int source_shard;\n",
        "  int binomial_count;\n",
        f"  std::array<BinomialEvent, {MAX_BINOMIALS}> binomials;\n",
        "  int row_event_count;\n",
        f"  std::array<RowEvent, {MAX_ROW_EVENTS}> row_events;\n",
        "};\n\n",
        "// Independently audited exact multi-row conjunction no-goods.\n",
        f"inline constexpr std::array<Cut, {len(bundle['cuts'])}> kVersion5{{{{\n",
    ]
    graph_counts = Counter()
    graph_literals = Counter()
    source_keys = set()
    event_fingerprints = set()
    for index, cut in enumerate(bundle["cuts"]):
        assert cut["id"] == f"laurent-event-cut-{index}"
        assert cut["graph"] in MATCHING_LIMITS
        assert cut["source_run"] in {"run-061", "run-063", "run-064"}
        assert isinstance(cut["source_shard"], int) and cut["source_shard"] >= 0
        assert re.fullmatch(r"[0-9a-f]{64}", cut["source_sha256"])
        source_key = (
            cut["source_run"], cut["graph"], cut["source_shard"],
            cut["source_sha256"],
        )
        assert source_key not in source_keys
        source_keys.add(source_key)
        graph_counts[cut["graph"]] += 1
        events = cut["binomial_events"]
        assert 0 <= len(events) <= MAX_BINOMIALS
        assert len({(item["state"], item["left"], item["right"]) for item in events}) == len(events)
        assert len({item["state"] for item in events}) == len(events)
        for event in events:
            assert 0 <= event["state"] < 3**8
            assert 0 <= event["left"] < event["right"] < MATCHING_LIMITS[cut["graph"]]
        padded_events = [
            f'{{{event["state"]}, {event["left"]}, {event["right"]}}}'
            for event in events
        ] + ["{-1, -1, -1}"] * (MAX_BINOMIALS - len(events))

        row_events = cut["row_events"]
        assert 1 <= len(row_events) <= MAX_ROW_EVENTS
        assert len({item["state"] for item in row_events}) == len(row_events)
        assert {item["state"] for item in events}.isdisjoint(
            item["state"] for item in row_events
        )
        rendered_rows = []
        for event in row_events:
            matchings = event["supported_matchings"]
            assert 3 <= len(matchings) <= MAX_ROW_TERMS
            assert len(set(matchings)) == len(matchings)
            assert matchings == sorted(matchings)
            assert 0 <= event["state"] < 3**8
            assert all(0 <= item < MATCHING_LIMITS[cut["graph"]] for item in matchings)
            padded = matchings + [-1] * (MAX_ROW_TERMS - len(matchings))
            rendered_rows.append(
                "{" + f'{event["state"]}, {len(matchings)}, '
                + "{{" + ", ".join(map(str, padded)) + "}}}"
            )
        rendered_rows += [
            "{-1, 0, {{" + ", ".join(["-1"] * MAX_ROW_TERMS) + "}}}"
        ] * (MAX_ROW_EVENTS - len(row_events))
        event_fingerprint = json.dumps(
            {
                "graph": cut["graph"],
                "binomial_events": events,
                "row_events": row_events,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        assert event_fingerprint not in event_fingerprints
        event_fingerprints.add(event_fingerprint)
        graph_literals[cut["graph"]] += 3 * len(events) + sum(
            1 + len(event["supported_matchings"]) for event in row_events
        )
        result.extend([
            "    {\n",
            f'        "{cut["graph"]}",\n',
            f'        {cut["source_shard"]},\n',
            f"        {len(events)},\n",
            "        {{" + ", ".join(padded_events) + "}},\n",
            f"        {len(row_events)},\n",
            "        {{" + ", ".join(rendered_rows) + "}},\n",
            "    },\n",
        ])
    assert graph_counts == {"C4+C4": 17, "C5+C3": 7, "C8": 19}
    assert graph_literals == EXPECTED_NEW_LITERALS
    result.extend(["}};\n\n", "}  // namespace exact_event_cuts_v5\n"])
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
        "cuts": 43,
        "literals": sum(EXPECTED_NEW_LITERALS.values()),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
