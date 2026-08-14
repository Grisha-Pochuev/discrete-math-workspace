#!/usr/bin/env python3
"""Synthetic end-to-end contract test for the run-082 certificate pipeline."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
PAIRS = (
    (8, 32), (8, 104), (18, 42), (18, 114), (19, 43), (19, 115),
    (32, 104), (42, 114), (43, 115), (48, 72), (52, 76), (64, 88),
    (65, 89), (68, 92), (69, 93), (71, 95),
)


def digest(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def run(*arguments):
    subprocess.run([sys.executable, *map(str, arguments)], check=True)


def main():
    with tempfile.TemporaryDirectory(prefix="run082-contract-") as temporary:
        root = Path(temporary)
        certificate_dir = root / "certificates"
        certificate_dir.mkdir()
        systems = []
        for pair in PAIRS:
            system = {
                "bits": list(pair),
                "effective_rank": 1,
                "generators": [
                    {
                        "term_count": 2,
                        "polynomial": [
                            {"exponent": [0], "coefficient": "-1"},
                            {"exponent": [1], "coefficient": "1"},
                        ],
                    },
                    {
                        "term_count": 2,
                        "polynomial": [
                            {"exponent": [0], "coefficient": "-2"},
                            {"exponent": [1], "coefficient": "1"},
                        ],
                    },
                ],
            }
            system["system_sha256"] = digest(system)
            systems.append(system)
        spec = {
            "schema": "torus-residue-systems-v1",
            "evidence_level": "synthetic contract input",
            "system_count": len(systems),
            "systems": systems,
            "outcome_rule": "synthetic",
        }
        spec["canonical_outcome_sha256"] = digest(spec)
        spec_path = root / "spec.json"
        spec_path.write_text(
            json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        for pair in PAIRS:
            certificate = certificate_dir / f"certificate-{pair[0]}-{pair[1]}.json"
            run(
                HERE / "run082_torus_certificate.py",
                "--spec", spec_path,
                "--spec-sha", spec["canonical_outcome_sha256"],
                "--pair", f"{pair[0]},{pair[1]}",
                "--output", certificate,
            )
            run(
                HERE / "run082_torus_replay.py",
                "--spec", spec_path,
                "--spec-sha", spec["canonical_outcome_sha256"],
                "--certificate", certificate,
            )
        output = root / "accepted"
        run(
            HERE / "run082_torus_collect.py",
            "--spec", spec_path,
            "--spec-sha", spec["canonical_outcome_sha256"],
            "--certificate-dir", certificate_dir,
            "--output-dir", output,
        )
        summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
        if summary["identity_count"] != 16 or len(summary["records"]) != 16:
            raise AssertionError("synthetic collector coverage mismatch")
        print(json.dumps({"accepted": True, "synthetic_identities": 16}))


if __name__ == "__main__":
    main()
