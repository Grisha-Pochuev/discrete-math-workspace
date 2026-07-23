#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import batch


def load_frontier3_tasks() -> list[batch.Task]:
    candidates = sorted((Path(__file__).parent / "runs").glob("*/next_tasks.json"))
    if not candidates:
        raise RuntimeError("no saved next_tasks.json")
    document = json.loads(candidates[-1].read_text(encoding="utf-8"))
    if document.get("stage") != "frontier3":
        raise RuntimeError(f"unexpected next frontier stage: {document.get('stage')}")
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
        for item in document["tasks"]
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
