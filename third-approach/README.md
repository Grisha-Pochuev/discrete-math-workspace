# Third approach

This directory contains the third computational experiment track.

It uses a proof-oriented search architecture and is kept separate from the numerical search tracks so its assumptions, state, and outputs remain independently auditable.

## Execution model

- 20 GitHub Actions jobs run in parallel.
- Each job uses four independent Python processes.
- The normal workflow budget is 21,000 seconds.
- Workers stop early enough to validate and upload artifacts safely.
- Compact summaries and retained candidates are committed under `runs/` and `candidates/`.
- A separate short smoke workflow checks executable-code changes before another long run.

## Adaptive selection

Later runs mix fresh search, refinement of strong retained candidates, and structurally diverse mutation. The committed bank preserves both strong and distinct candidates rather than only one lineage.

## Files

- `certificate.py` — local search model and candidate generation.
- `runner.py` — checkpointed worker driver.
- `collect.py` — aggregation and compact archival.
- `AGENTS.md` — operating and search rules.
- `control.json` — accepted-run state and policy parameters.
- `launch.json` — explicit one-run launch configuration.
- `candidates/` — retained candidate bank.
- `runs/` — committed run summaries.

Numerical output remains provisional until the corresponding exact or independent verification step succeeds.
