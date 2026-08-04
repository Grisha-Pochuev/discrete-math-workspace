#!/usr/bin/env python3
"""Configuration and manifest validation for Fourth approach."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

APPROACH = "fourth-approach-obstruction-guided-exact-synthesis"
SUPPORTED_TASKS = {
    "stage0_source_inventory",
    "stage1_canonicalize_verify",
    "stage2_minimize_certificates",
}
IMPLEMENTED_TASKS = {
    "stage0_source_inventory",
    "stage1_canonicalize_verify",
}
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


def validate_spec(
    data: dict[str, Any],
    launch: dict[str, Any] | None = None,
    *,
    require_ready: bool = False,
) -> dict[str, Any]:
    if int(data.get("schema_version", 0)) != 1:
        raise ValidationError("spec schema_version must be 1")
    run_index = int(data.get("run_index", -1))
    task = str(data.get("task", ""))
    if run_index < 0 or task not in SUPPORTED_TASKS:
        raise ValidationError("invalid spec run_index or task")
    for key in ("title", "research_question", "scientific_output", "next_decision"):
        if not str(data.get(key, "")).strip():
            raise ValidationError(f"spec.{key} is required")
    status = str(data.get("implementation_status", "ready" if task == "stage0_source_inventory" else ""))
    if require_ready:
        if status != "ready":
            raise ValidationError(f"spec is not implementation-ready: {status or 'missing'}")
        if task not in IMPLEMENTED_TASKS:
            raise ValidationError(f"runner does not implement task: {task}")
    execution = data.get("execution")
    if execution is not None:
        if not isinstance(execution, dict):
            raise ValidationError("spec.execution must be an object")
        jobs = int(execution.get("jobs", 0))
        minimum_jobs = int(execution.get("minimum_jobs", 0))
        runtime = int(execution.get("runtime_seconds", 0))
        attempts = int(execution.get("max_attempts", -1))
        if not 1 <= jobs <= MAX_JOBS:
            raise ValidationError("spec.execution.jobs is invalid")
        if not 1 <= minimum_jobs <= jobs:
            raise ValidationError("spec.execution.minimum_jobs is invalid")
        if not 30 <= runtime <= MAX_RUNTIME_SECONDS:
            raise ValidationError("spec.execution.runtime_seconds is invalid")
        if attempts < 0:
            raise ValidationError("spec.execution.max_attempts is invalid")
    if task == "stage1_canonicalize_verify" and status == "ready":
        archives = data.get("candidate_archives")
        if not isinstance(archives, list) or not archives:
            raise ValidationError("ready stage1 spec requires candidate_archives")
        for source in archives:
            if not isinstance(source, dict) or not str(source.get("path", "")).endswith(".json.gz"):
                raise ValidationError("invalid stage1 candidate archive declaration")
    if launch is not None:
        if run_index != launch["run_index"] or task != launch["task"]:
            raise ValidationError("launch and spec disagree on run_index/task")
        if execution is not None:
            for key in ("jobs", "minimum_jobs", "runtime_seconds", "max_attempts"):
                if int(execution[key]) != int(launch[key]):
                    raise ValidationError(f"launch and spec.execution disagree on {key}")
    normalized = dict(data)
    normalized["run_index"] = run_index
    normalized["task"] = task
    normalized["implementation_status"] = status
    return normalized


def launch_from_spec(spec_path: str, spec: dict[str, Any], *, enabled: bool = False, nonce: str) -> dict[str, Any]:
    execution = spec.get("execution")
    if not isinstance(execution, dict):
        raise ValidationError("next spec has no execution block")
    return validate_launch(
        {
            "schema_version": 1,
            "enabled": enabled,
            "run_index": int(spec["run_index"]),
            "task": str(spec["task"]),
            "spec_path": spec_path,
            "jobs": int(execution["jobs"]),
            "minimum_jobs": int(execution["minimum_jobs"]),
            "runtime_seconds": int(execution["runtime_seconds"]),
            "max_attempts": int(execution["max_attempts"]),
            "nonce": nonce,
        }
    )


def matrix_json(jobs: int) -> str:
    return json.dumps({"id": list(range(jobs))}, separators=(",", ":"))
