#!/usr/bin/env python3
"""Strictly replay and collect the complete run-082 certificate matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


HERE = Path(__file__).resolve().parent
REPLAY = HERE / "run082_torus_replay.py"


def canonical_digest(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def file_digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_hashed(path, expected=None):
    payload = json.loads(path.read_text(encoding="utf-8"))
    recorded = payload.pop("canonical_outcome_sha256")
    observed = canonical_digest(payload)
    payload["canonical_outcome_sha256"] = recorded
    if recorded != observed or (expected is not None and recorded != expected):
        raise AssertionError(f"canonical digest mismatch for {path}")
    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    parser.add_argument("--spec-sha", required=True)
    parser.add_argument("--certificate-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    spec_path = Path(args.spec)
    spec = load_hashed(spec_path, args.spec_sha)
    expected_pairs = {tuple(system["bits"]) for system in spec["systems"]}
    if len(expected_pairs) != 16 or int(spec["system_count"]) != 16:
        raise AssertionError("immutable specification does not contain sixteen systems")

    certificate_paths = sorted(Path(args.certificate_dir).rglob("certificate-*.json"))
    if len(certificate_paths) != len(expected_pairs):
        raise AssertionError(
            f"certificate coverage incomplete: expected {len(expected_pairs)}, "
            f"found {len(certificate_paths)}"
        )
    records = []
    observed_pairs = set()
    for certificate_path in certificate_paths:
        certificate = load_hashed(certificate_path)
        pair = tuple(certificate["pair"])
        if pair not in expected_pairs or pair in observed_pairs:
            raise AssertionError(f"unexpected or duplicate certificate pair {pair}")
        observed_pairs.add(pair)
        replay = subprocess.run(
            [
                sys.executable,
                str(REPLAY),
                "--spec", str(spec_path),
                "--spec-sha", args.spec_sha,
                "--certificate", str(certificate_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        replay_record = json.loads(replay.stdout.strip().splitlines()[-1])
        if replay_record.get("accepted") is not True or tuple(replay_record["pair"]) != pair:
            raise AssertionError(f"independent replay did not accept {pair}")
        records.append({
            "pair": list(pair),
            "certificate_file": f"certificate-{pair[0]}-{pair[1]}.json",
            "certificate_canonical_sha256": certificate["canonical_outcome_sha256"],
            "certificate_transport_sha256": file_digest(certificate_path),
            "certificate_terms_replayed": int(replay_record["certificate_terms_replayed"]),
            "seconds": float(certificate["seconds"]),
            "basis_size_before_one": int(certificate["basis_size_before_one"]),
            "s_pairs_processed": int(certificate["s_pairs_processed"]),
            "coprime_s_pairs_skipped": int(certificate["coprime_s_pairs_skipped"]),
        })
    if observed_pairs != expected_pairs:
        raise AssertionError("certificate pair coverage has a gap")
    records.sort(key=lambda record: record["pair"])

    output = Path(args.output_dir)
    if output.exists() and any(output.iterdir()):
        raise AssertionError("collector output directory is not empty")
    output.mkdir(parents=True, exist_ok=True)
    copied_spec = output / spec_path.name
    shutil.copy2(spec_path, copied_spec)
    source_by_pair = {
        tuple(load_hashed(path)["pair"]): path for path in certificate_paths
    }
    for record in records:
        pair = tuple(record["pair"])
        shutil.copy2(source_by_pair[pair], output / record["certificate_file"])

    summary = {
        "schema": "run-082-torus-certificate-bundle-v1",
        "evidence_level": "complete independently replayed exact identity matrix",
        "spec_file": copied_spec.name,
        "spec_canonical_sha256": args.spec_sha,
        "system_count": len(records),
        "identity_count": len(records),
        "certificate_terms_replayed": sum(
            record["certificate_terms_replayed"] for record in records
        ),
        "records": records,
        "conclusion": "all sixteen immutable systems have an exact identity equal to one",
    }
    summary["canonical_outcome_sha256"] = canonical_digest(summary)
    summary_path = output / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    checksum_paths = [copied_spec, summary_path] + [
        output / record["certificate_file"] for record in records
    ]
    (output / "CHECKSUMS.sha256").write_text(
        "".join(f"{file_digest(path)}  {path.name}\n" for path in checksum_paths),
        encoding="utf-8",
    )
    print(json.dumps({
        "accepted": True,
        "system_count": len(records),
        "certificate_terms_replayed": summary["certificate_terms_replayed"],
        "canonical_outcome_sha256": summary["canonical_outcome_sha256"],
        "output_dir": str(output),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
