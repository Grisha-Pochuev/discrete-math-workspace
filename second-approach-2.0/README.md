# Second approach 2.0

This directory is a revised continuation of `second-approach/` with a broader multi-lineage search policy.

## Execution model

- Long runs use 20 GitHub Actions jobs with four single-threaded workers per job.
- The normal runtime budget is 21,000 seconds per job.
- Runs are checkpointed and collected into compact archives.
- Accepted archives are stored under `runs/`.
- The compact cross-run bank is stored under `candidates/`.
- `launch.json` starts exactly one configured long run.
- `control.json` stores durable state.

## Search layout

The worker pool is split across several independent and inherited lanes so one lineage does not dominate all compute. Lane assignments, parent handling, diversity checks, and archive verification are implemented in the local source files.

## Files

- `AGENTS.md` — operating rules for automated tracking.
- `engine.py` — lane assignment and candidate handling.
- `runner.py` — checkpointed worker driver.
- `collect.py` — aggregation and archive creation.
- `verify_run.py` — offline consistency verification.
- `control.json` — durable state.
- `launch.json` — explicit launch configuration.

## Operating principle

Continuation is controlled by whether new runs add useful independent information. Do not launch overlapping large matrices, and do not interpret a low numerical score as independently verified output without the corresponding verification step.
