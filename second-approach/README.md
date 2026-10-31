# Second approach

This directory contains the second computational experiment track.

It is intentionally isolated from the original exact-search archives so its assumptions, state, and outputs can be reviewed independently.

## Directory layout

- `plans/` — experiment designs and run notes;
- `runs/` — one subdirectory per compute run;
- `candidates/` — compact retained records;
- `analysis/` — comparisons and post-run analysis;
- `schemas/` — stable formats for configurations and results;
- `control.json` — durable run state;
- `model.py`, `runner.py`, `collect.py`, `verify_run.py` — execution and verification code.

## Operating principles

1. Preserve reproducible inputs, deterministic seeds, configurations, and checksums.
2. Keep heuristic output distinct from independently verified output.
3. Preserve unusual or unresolved records instead of retaining only the current numerical leader.
4. Do not mix this track's archives with the other approach directories.
5. Before any large run, inspect all active GitHub Actions jobs and avoid overlapping large matrices.
