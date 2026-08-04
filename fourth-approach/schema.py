#!/usr/bin/env python3
"""Configuration and manifest validation for Fourth approach."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

APPROACH = "fourth-approach-obstruction-guided-exact-synthesis"
SUPPORTED_TASKS = {"stage0_source_inventory"}
MAX_JOBS = 20
MAX_RUNTIME_SECONDS = 20_700


class ValidationError(ValueError):
    pass


def read_json(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"missing JSON file: {p}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON in {p}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValidationError(f"expected JSON object in {p}")
    return data


def validate_launch(data: dict[str, Any]) -> dict[str, Any]:
    if int(data.get("schema_version", 0)) != 1:
        raise ValidationError("launch schema_version must be 1")
    enabled = data.get("enabled")
    if not isinstance(enabled, bool):
        raise ValidationError("launch.enabled must be boolean")
    run_index = int(data.get("run_index", -1))
    if run_index < 0:
        raise ValidationError("run_index must be non-negative")
    task = str(data.get("task", ""))
    if task not in SUPPORTED_TASKS:
        raise ValidationError(f"unsupported task: {task}")
    spec_path = str(data.get("spec_path", ""))
    if not spec_path.startswith("fourth-approach/run-specs/") or not spec_path.endswith(".json"):
        raise ValidationError("spec_path must point into fourth-approach/run-specs")
    jobs = int(data.get("jobs", 0))
    minimum_jobs = int(data.get("minimum_jobs", 0))
    if not 1 <= jobs <= MAX_JOBS:
        raise ValidationError(f"jobs must be between 1 and {MAX_JOBS}")
    if not 1 <= minimum_jobs <= jobs:
        raise ValidationError("minimum_jobs must be between 1 and jobs")
    runtime = int(data.get("runtime_seconds", 0))
    if not 30 <= runtime <= MAX_RUNTIME_SECONDS:
        raise ValidationError(f"runtime_seconds must be 30..{MAX_RUNTIME_SECONDS}")
    attempts = int(data.get("max_attempts", -1))
    if attempts < 0:
        raise ValidationError("max_attempts must be non-negative")
    nonce = str(data.get("nonce", ""))
    if len(nonce) < 12:
        raise ValidationError("nonce must be unique and at least 12 characters")
    normalized = dict(data)
    normalized.update(
        enabled=enabled,
        run_index=run_index,
        task=task,
        spec_path=spec_path,
        jobs=jobs,
        minimum_jobs=minimum_jobs,
        runtime_seconds=runtime,
        max_attempts=attempts,
        nonce=nonce,
    )
    return normalized


def validate_spec(data: dict[str, Any], launch: dict[str, Any] | None = None) -> dict[str, Any]:
    if int(data.get("schema_version", 0)) != 1:
        raise ValidationError("spec schema_version must be 1")
    run_index = int(data.get("run_index", -1))
    task = str(data.get("task", ""))
    if run_index < 0 or task not in SUPPORTED_TASKS:
        raise ValidationError("invalid spec run_index or task")
    for key in ("title", "research_question", "scientific_output", "next_decision"):
        if not str(data.get(key, "")).strip():
            raise ValidationError(f"spec.{key} is required")
    if launch is not None:
        if run_index != launch["run_index"] or task != launch["task"]:
            raise ValidationError("launch and spec disagree on run_index/task")
    return dict(data)


def matrix_json(jobs: int) -> str:
    return json.dumps({"id": list(range(jobs))}, separators=(",", ":"))
