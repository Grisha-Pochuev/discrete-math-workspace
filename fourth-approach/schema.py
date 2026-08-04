#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

APPROACH = "fourth-approach-obstruction-guided-exact-synthesis"
SUPPORTED_TASKS = {"stage2_minimize_certificates"}
MAX_JOBS = 20
MAX_RUNTIME_SECONDS = 20700

class ValidationError(ValueError):
    pass

def read_json(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    try:
        value = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"missing JSON file: {p}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON in {p}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"expected object in {p}")
    return value

def validate_launch(data: dict[str, Any]) -> dict[str, Any]:
    if int(data.get("schema_version", 0)) != 1:
        raise ValidationError("launch schema_version must be 1")
    if not isinstance(data.get("enabled"), bool):
        raise ValidationError("launch.enabled must be boolean")
    task = str(data.get("task", ""))
    if task not in SUPPORTED_TASKS:
        raise ValidationError(f"unsupported task: {task}")
    run_index = int(data.get("run_index", -1))
    jobs = int(data.get("jobs", 0))
    minimum_jobs = int(data.get("minimum_jobs", 0))
    runtime = int(data.get("runtime_seconds", 0))
    max_attempts = int(data.get("max_attempts", -1))
    nonce = str(data.get("nonce", ""))
    spec_path = str(data.get("spec_path", ""))
    if run_index != 2:
        raise ValidationError("manual launch must be run 002")
    if jobs != 20 or not 18 <= minimum_jobs <= 20:
        raise ValidationError("run 002 must use 20 jobs and minimum_jobs 18..20")
    if runtime != 20700:
        raise ValidationError("run 002 runtime_seconds must be 20700")
    if max_attempts < 0:
        raise ValidationError("max_attempts must be non-negative")
    if len(nonce) < 12:
        raise ValidationError("nonce too short")
    if spec_path != "fourth-approach/run-specs/run-002-stage2-minimize-certificates.json":
        raise ValidationError("unexpected run 002 spec path")
    return {
        **data,
        "run_index": run_index,
        "jobs": jobs,
        "minimum_jobs": minimum_jobs,
        "runtime_seconds": runtime,
        "max_attempts": max_attempts,
        "task": task,
        "nonce": nonce,
        "spec_path": spec_path,
    }

def validate_spec(data: dict[str, Any], launch: dict[str, Any] | None = None, *, require_ready: bool = False) -> dict[str, Any]:
    if int(data.get("schema_version", 0)) != 1:
        raise ValidationError("spec schema_version must be 1")
    if int(data.get("run_index", -1)) != 2 or str(data.get("task", "")) not in SUPPORTED_TASKS:
        raise ValidationError("invalid run 002 spec")
    if require_ready and data.get("implementation_status") != "ready":
        raise ValidationError("run 002 spec is not ready")
    for key in ("title", "research_question", "scientific_output", "next_decision", "source_canonical_classes"):
        if not str(data.get(key, "")).strip():
            raise ValidationError(f"spec.{key} is required")
    archives = data.get("candidate_archives")
    if not isinstance(archives, list) or not archives:
        raise ValidationError("candidate_archives are required")
    execution = data.get("execution")
    if not isinstance(execution, dict):
        raise ValidationError("execution is required")
    if int(execution.get("jobs", 0)) != 20 or int(execution.get("runtime_seconds", 0)) != 20700:
        raise ValidationError("invalid run 002 execution")
    if launch is not None:
        for key in ("run_index", "task"):
            if data[key] != launch[key]:
                raise ValidationError(f"launch/spec mismatch: {key}")
        for key in ("jobs", "minimum_jobs", "runtime_seconds", "max_attempts"):
            if int(execution[key]) != int(launch[key]):
                raise ValidationError(f"launch/spec mismatch: {key}")
    return dict(data)

def matrix_json(jobs: int) -> str:
    return json.dumps({"id": list(range(jobs))}, separators=(",", ":"))
