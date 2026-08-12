#!/usr/bin/env python3
"""Create a content-equivalent neutral immutable input bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def write(path, value, *, compact=False):
    if compact:
        text = json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    else:
        text = json.dumps(value, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--types-source", type=Path, required=True)
    parser.add_argument("--input-source", type=Path, required=True)
    parser.add_argument("--acceptance-source", type=Path, required=True)
    parser.add_argument("--types-output", type=Path, required=True)
    parser.add_argument("--input-output", type=Path, required=True)
    parser.add_argument("--acceptance-output", type=Path, required=True)
    parser.add_argument("--hint-source", type=Path, required=True)
    parser.add_argument("--hint-output", type=Path, required=True)
    args = parser.parse_args()

    types = json.loads(args.types_source.read_text(encoding="utf-8"))
    data = json.loads(args.input_source.read_text(encoding="utf-8"))
    acceptance = json.loads(args.acceptance_source.read_text(encoding="utf-8"))
    hint = json.loads(args.hint_source.read_text(encoding="utf-8"))
    types["schema"] = "run-073-type-catalogue-v1"
    data["schema"] = "run-073-input-v1"
    acceptance["schema"] = "run-073-input-acceptance-v1"
    acceptance["source_types_sha256"] = acceptance.pop("types_sha256")
    acceptance["source_manifest_sha256"] = acceptance.pop("manifest_sha256")
    acceptance.pop("canonical_acceptance_sha256", None)
    write(args.types_output, types)
    write(args.input_output, data, compact=True)
    acceptance["types_sha256"] = hashlib.sha256(args.types_output.read_bytes()).hexdigest()
    acceptance["manifest_sha256"] = hashlib.sha256(args.input_output.read_bytes()).hexdigest()
    write(args.acceptance_output, acceptance)
    neutral_hint = {
        "schema": "run-073-support-hint-v1",
        "types_sha256": hashlib.sha256(args.types_output.read_bytes()).hexdigest(),
        "manifest_sha256": hashlib.sha256(args.input_output.read_bytes()).hexdigest(),
        "type_index": hint["type_index"],
        "fourth_index": hint["fourth_index"],
        "support_cost": hint["support_cost"],
        "active_pure_extras": hint["active_pure_extras"],
        "active_fourth_entries": hint["active_fourth_entries"],
    }
    write(args.hint_output, neutral_hint)


if __name__ == "__main__":
    main()
