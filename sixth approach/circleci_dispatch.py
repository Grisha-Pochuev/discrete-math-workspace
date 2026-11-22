#!/usr/bin/env python3
"""Dispatch one explicitly parameterized CircleCI short-pool run."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request
import uuid


def load_spec(path: Path) -> dict:
    spec = json.loads(path.read_text(encoding="utf-8"))
    if spec.get("schema_version") != 1:
        raise ValueError("unexpected specification schema")
    if spec.get("provider") != "circleci" or spec.get("trigger") != "api":
        raise ValueError("specification is not an API-triggered CircleCI run")
    slug = spec.get("project_slug")
    if not isinstance(slug, str) or not slug.startswith("circleci/") or slug.count("/") != 2:
        raise ValueError("invalid project slug")
    uuid.UUID(spec.get("pipeline_definition_id", ""))
    parameter = spec.get("pipeline_parameter")
    expected_parameter = {"name": spec["run_id"].replace("-", "_"), "value": True}
    if parameter != expected_parameter:
        raise ValueError("invalid pipeline parameter")
    if spec.get("config_ref") != "main" or spec.get("checkout_ref") != "main":
        raise ValueError("unexpected config or checkout ref")
    return spec


def request_payload(spec: dict) -> dict:
    parameter = spec["pipeline_parameter"]
    return {
        "definition_id": spec["pipeline_definition_id"],
        "config": {"branch": spec["config_ref"]},
        "checkout": {"branch": spec["checkout_ref"]},
        "parameters": {parameter["name"]: parameter["value"]},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm", help="must equal the immutable run identifier")
    args = parser.parse_args()

    spec = load_spec(args.spec)
    payload = request_payload(spec)
    endpoint = f"https://circleci.com/api/v2/project/{spec['project_slug']}/pipeline/run"
    if args.dry_run:
        print(json.dumps({"endpoint": endpoint, "payload": payload}, indent=2, sort_keys=True))
        return 0
    if args.confirm != spec["run_id"]:
        raise ValueError("explicit run confirmation is required")
    token = os.environ.get("CIRCLE_TOKEN")
    if not token:
        raise ValueError("CIRCLE_TOKEN is not set")

    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={
            "Circle-Token": token,
            "Content-Type": "application/json",
            "User-Agent": "neutral-short-pool-dispatcher/1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            result = json.loads(body) if body else {"status": response.status}
    except urllib.error.HTTPError as error:
        message = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"CircleCI API returned HTTP {error.code}: {message}") from error
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
