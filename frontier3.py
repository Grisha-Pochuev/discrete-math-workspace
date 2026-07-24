#!/usr/bin/env python3
from __future__ import annotations

import gzip
import json
from pathlib import Path

import batch


def load_json(path: Path) -> dict[str, object]:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as source:
            document = json.load(source)
    else:
        document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise RuntimeError(f"expected JSON object in {path}")
    return document


def load_frontier3_tasks() -> list[batch.Task]:
    runs = Path(__file__).parent / "runs"
    candidates = sorted([*runs.glob("*/next_tasks.json"), *runs.glob("*/next_tasks.json.gz")])
    if not candidates:
        raise RuntimeError("no saved next_tasks.json or next_tasks.json.gz")
    document = load_json(candidates[-1])
    if document.get("stage") != "frontier3":
        raise RuntimeError(f"unexpected next frontier stage: {document.get('stage')}")
    raw_tasks = document.get("tasks")
    if not isinstance(raw_tasks, list):
        raise RuntimeError(f"task list missing in {candidates[-1]}")
    tasks = [
        batch.Task(
            str(item["stage"]),
            int(item["orbit"]),
            int(item["limit"]),
            int(item["shard"]),
            int(item["shards"]),
            int(item.get("split", 15)),
            int(item.get("max_seen", 0)),
        )
        for item in raw_tasks
    ]
    names = [task.name for task in tasks]
    if len(names) != len(set(names)):
        raise RuntimeError("duplicate frontier3 task names")
    return tasks


# Reuse the resource monitor and process driver in batch.py without changing the
# old frontier2 workflow. batch.all_tasks resolves this module attribute at run time.
batch.frontier2_tasks = load_frontier3_tasks


if __name__ == "__main__":
    raise SystemExit(batch.main())
