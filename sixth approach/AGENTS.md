# Sixth approach operating rules

This directory is an isolated computational track. Do not import mutable state
from earlier tracks and do not edit their accepted archives.

Public names, logs, workflow titles, artifact names, and commit messages must
remain neutral. Mathematical motivation belongs only in the private analysis
tree, not in this repository.

## Required run discipline

- `control.json` is the only mutable run-control record.
- Every run is specified by an immutable JSON file under `specs/`.
- Heavy work is C++20. Python is permitted only for validation and collection.
- A smoke run must compile and execute the same worker binary and output path as
  a full run.
- Full runs are manual `workflow_dispatch` jobs only. Never add a `push` trigger.
- Use exactly four independent single-threaded workers per Actions job.
- Worker output is checkpointed atomically and is collected with `if: always()`.
- The collector must reject missing/duplicate shards and incomplete exact
  coverage. Scientific counterexamples are data, not technical failures.
- Before a large run, inspect all queued, pending, waiting, requested, and
  in-progress Actions jobs on every branch and workflow.
- Never run an individual local computation for more than 15 minutes.

## Archive contract

An accepted archive contains the immutable spec, all worker JSON files, a
machine-generated summary, selected frontier records, and SHA-256 checksums.
Acceptance means only that the declared computation was technically complete.

